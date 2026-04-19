"""GTK4 + libadwaita window for GUI Speed Test for Linux.

Kept in its own module so the CLI/JSON paths don't pay for GI imports, and
so the window code can evolve without churning the entry-point file.
"""
from __future__ import annotations

import logging
import os
import threading
from collections import deque
from pathlib import Path

from backends import available_backends, display_name_for, get_backend
from backends.base import BackendError, format_speed

logger = logging.getLogger("gui_speedtest")

# Accent colour used by the speed-card charts and ping bars. Matches the
# orange of the Start button so the graph visually ties to the action.
_CHART_ACCENT = (0.90, 0.38, 0.10)  # ~ libadwaita "orange-4"


def _log_file_path() -> Path:
    """Duplicated from gui_speedtest so this module has no back-import.
    Must stay in sync with _log_path() there."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "gui-speedtest" / "gui-speedtest.log"


def run_gui(
    backend_name: str, app_name: str, app_id: str, app_version: str, latency_samples: int
) -> None:
    # `import cairo` up-front registers the pygobject foreign-struct
    # converter for cairo.Context — without it, any Gtk.DrawingArea
    # draw_func callback raises
    #   "TypeError: Couldn't find foreign struct converter for 'cairo.Context'"
    # silently inside GTK's paint pipeline, and the widget never draws.
    # The debian package pulls python3-gi-cairo as a hard dep so this
    # import succeeds; pip users need to install it separately.
    import cairo  # noqa: F401

    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gio, GLib, Gtk, Pango

    class _Sparkline(Gtk.DrawingArea):
        """Rolling line chart of recent speed samples.

        Used inside the download and upload speed cards to show live
        throughput history without claiming more screen real estate.
        Auto-scales Y to max-in-window; fills under the line at low
        alpha so the big number on top stays readable."""

        def __init__(self, max_points: int = 120) -> None:
            super().__init__()
            self._samples: deque[float] = deque(maxlen=max_points)
            self.set_content_height(38)
            self.set_hexpand(True)
            self.set_draw_func(self._draw)

        def add_sample(self, value: float) -> None:
            self._samples.append(max(float(value), 0.0))
            self.queue_draw()

        def clear(self) -> None:
            self._samples.clear()
            self.queue_draw()

        def _draw(self, _area, cr, width: int, height: int) -> None:
            if len(self._samples) < 2:
                return
            peak = max(self._samples)
            if peak <= 0:
                return
            r, g, b = _CHART_ACCENT
            n = len(self._samples)
            step = width / (n - 1)
            cr.set_line_width(1.5)
            cr.set_source_rgb(r, g, b)
            cr.move_to(0, height - (self._samples[0] / peak) * (height - 2) - 1)
            for i, v in enumerate(self._samples):
                cr.line_to(i * step, height - (v / peak) * (height - 2) - 1)
            cr.stroke_preserve()
            # Fill underneath — low alpha so the speed number above is
            # still the visual focus.
            cr.line_to(width, height)
            cr.line_to(0, height)
            cr.close_path()
            cr.set_source_rgba(r, g, b, 0.18)
            cr.fill()

    class _PingBars(Gtk.DrawingArea):
        """Per-sample latency bars — one thin vertical bar per ping.
        Shows both the average spread (jitter) and any outliers in a
        glance. Auto-scales Y to max-seen ping."""

        def __init__(self, expected_samples: int = 10) -> None:
            super().__init__()
            self._samples: list[float] = []
            self._capacity = expected_samples
            self.set_content_height(28)
            self.set_hexpand(True)
            self.set_draw_func(self._draw)

        def add_sample(self, value_ms: float) -> None:
            self._samples.append(max(float(value_ms), 0.0))
            self.queue_draw()

        def clear(self) -> None:
            self._samples.clear()
            self.queue_draw()

        def _draw(self, _area, cr, width: int, height: int) -> None:
            if not self._samples:
                return
            peak = max(self._samples) or 1.0
            slots = max(self._capacity, len(self._samples))
            # Each bar occupies 1/slots of the width with a 2px gutter.
            bar_w = max(2.0, (width / slots) - 2)
            r, g, b = _CHART_ACCENT
            cr.set_source_rgb(r, g, b)
            for i, v in enumerate(self._samples):
                bar_h = max(1.0, (v / peak) * (height - 2))
                x = i * (bar_w + 2)
                cr.rectangle(x, height - bar_h, bar_w, bar_h)
            cr.fill()

    class SpeedTestWindow(Adw.ApplicationWindow):
        def __init__(self, app: Adw.Application, initial_backend: str) -> None:
            super().__init__(application=app, title=app_name)
            # Default size picked to show every control on first open
            # without scrolling: speed cards (now with sparklines, ~170px),
            # latency row (with ping bars, ~120px), 5 connection rows,
            # progress + status + button + margins ~= 920 px tall.
            self.set_default_size(600, 940)
            # Floor — stops the user accidentally shrinking the window to
            # a state where the cards overlap or the Start button is
            # hidden. ScrolledWindow handles anything taller gracefully.
            self.set_size_request(500, 680)
            self.running = False
            self.backends = available_backends()
            if initial_backend not in self.backends:
                initial_backend = self.backends[0]
            self.backend = get_backend(initial_backend)
            self.cancelled = False

            self.connect("close-request", self._on_close)

            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.set_content(main_box)

            header = Adw.HeaderBar()
            header.set_title_widget(
                Adw.WindowTitle(title=app_name, subtitle=f"v{app_version}")
            )
            # Log button — opens an in-app viewer so users don't need a
            # terminal to diagnose issues or share a trace with support.
            log_btn = Gtk.Button(label="Log", tooltip_text="View application log")
            log_btn.connect("clicked", self._on_show_log)
            header.pack_end(log_btn)
            main_box.append(header)

            scroll = Gtk.ScrolledWindow(vexpand=True)
            scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            main_box.append(scroll)

            content = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=16,
                margin_top=24,
                margin_bottom=24,
                margin_start=24,
                margin_end=24,
            )
            scroll.set_child(content)

            speed_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=16,
                halign=Gtk.Align.FILL,
                hexpand=True,
                homogeneous=True,
            )
            content.append(speed_row)

            self.dl_card = self._make_speed_card("Download")
            self.ul_card = self._make_speed_card("Upload")
            speed_row.append(self.dl_card["frame"])
            speed_row.append(self.ul_card["frame"])

            lat_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=16,
                halign=Gtk.Align.FILL,
                hexpand=True,
                homogeneous=True,
            )
            content.append(lat_row)

            self.ping_card = self._make_stat_card("Ping", with_bars=True)
            self.jitter_card = self._make_stat_card("Jitter")
            lat_row.append(self.ping_card["frame"])
            lat_row.append(self.jitter_card["frame"])

            info_group = Adw.PreferencesGroup(title="Connection")
            content.append(info_group)

            backend_labels = Gtk.StringList()
            for name in self.backends:
                backend_labels.append(display_name_for(name))
            self.backend_row = Adw.ComboRow(title="Backend", model=backend_labels)
            self.backend_row.set_selected(self.backends.index(self.backend.name))
            self.backend_row.connect("notify::selected", self._on_backend_changed)
            self.ip_row = Adw.ActionRow(title="IP Address", subtitle="—")
            self.isp_row = Adw.ActionRow(title="ISP", subtitle="—")
            self.loc_row = Adw.ActionRow(title="Location", subtitle="—")
            self.server_row = Adw.ActionRow(title="Server", subtitle="—")
            info_group.add(self.backend_row)
            # "Enable Ookla" row — only shown when the Ookla backend is in
            # REGISTRY but not in the available list (i.e. the official
            # `speedtest` binary isn't on PATH). Lets users enable it with
            # one click (polkit password prompt) instead of dropping to a
            # terminal for `sudo gui-speedtest-install-ookla`.
            self.info_group = info_group
            self._ookla_row = self._make_enable_ookla_row()
            if self._needs_ookla_enable():
                info_group.add(self._ookla_row)
            info_group.add(self.ip_row)
            info_group.add(self.isp_row)
            info_group.add(self.loc_row)
            info_group.add(self.server_row)

            self.progress = Gtk.ProgressBar(show_text=True, margin_top=8)
            self.progress.set_text("Ready")
            content.append(self.progress)

            self.status = Gtk.Label(
                label="Press Start to begin",
                css_classes=["dim-label"],
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
                max_width_chars=60,
                justify=Gtk.Justification.CENTER,
            )
            content.append(self.status)

            self.start_btn = Gtk.Button(
                label="Start Speed Test",
                css_classes=["suggested-action", "pill"],
                halign=Gtk.Align.CENTER,
                margin_top=8,
            )
            self.start_btn.set_size_request(200, -1)
            self.start_btn.connect("clicked", self._on_start)
            content.append(self.start_btn)

            css = Gtk.CssProvider()
            css.load_from_string(
                """
                .speed-value { font-size: 28px; font-weight: 800; }
                .speed-unit { font-size: 13px; font-weight: 400; }
                .speed-label { font-size: 12px; font-weight: 600; letter-spacing: 1px; }
                .stat-value { font-size: 22px; font-weight: 700; }
                .stat-unit { font-size: 12px; }
                .speed-card { padding: 20px 28px; border-radius: 12px; }
                .stat-card { padding: 14px 24px; border-radius: 10px; }
                .speed-error, .stat-error { font-size: 11px; margin-top: 4px; }
                """
            )
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        def _make_speed_card(self, label: str) -> dict:
            frame = Gtk.Frame(
                css_classes=["speed-card"],
                hexpand=True,
                halign=Gtk.Align.FILL,
            )
            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=4,
                halign=Gtk.Align.FILL,
            )
            frame.set_child(box)
            box.append(
                Gtk.Label(
                    label=label.upper(),
                    css_classes=["speed-label", "dim-label"],
                    halign=Gtk.Align.CENTER,
                )
            )
            val_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=4,
                halign=Gtk.Align.CENTER,
            )
            box.append(val_box)
            val = Gtk.Label(label="—", css_classes=["speed-value"])
            unit = Gtk.Label(
                label="Mbps",
                css_classes=["speed-unit", "dim-label"],
                valign=Gtk.Align.END,
                margin_bottom=4,
            )
            val_box.append(val)
            val_box.append(unit)
            chart = _Sparkline()
            box.append(chart)
            error_lbl = Gtk.Label(
                label="",
                visible=False,
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
                max_width_chars=28,
                xalign=0.5,
                justify=Gtk.Justification.CENTER,
                css_classes=["speed-error", "dim-label"],
            )
            box.append(error_lbl)
            return {"frame": frame, "value": val, "unit": unit, "chart": chart, "error": error_lbl}

        def _make_stat_card(self, label: str, with_bars: bool = False) -> dict:
            frame = Gtk.Frame(
                css_classes=["stat-card"],
                hexpand=True,
                halign=Gtk.Align.FILL,
            )
            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=2,
                halign=Gtk.Align.FILL,
            )
            frame.set_child(box)
            box.append(
                Gtk.Label(
                    label=label.upper(),
                    css_classes=["speed-label", "dim-label"],
                    halign=Gtk.Align.CENTER,
                )
            )
            val_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=3,
                halign=Gtk.Align.CENTER,
            )
            box.append(val_box)
            val = Gtk.Label(label="—", css_classes=["stat-value"])
            unit = Gtk.Label(
                label="ms",
                css_classes=["stat-unit", "dim-label"],
                valign=Gtk.Align.END,
                margin_bottom=2,
            )
            val_box.append(val)
            val_box.append(unit)
            out = {"frame": frame, "value": val, "unit": unit}
            if with_bars:
                bars = _PingBars(expected_samples=latency_samples)
                box.append(bars)
                out["bars"] = bars
            error_lbl = Gtk.Label(
                label="",
                visible=False,
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
                max_width_chars=22,
                xalign=0.5,
                justify=Gtk.Justification.CENTER,
                css_classes=["stat-error", "dim-label"],
            )
            box.append(error_lbl)
            out["error"] = error_lbl
            return out

        def _update_speed(self, card: dict, speed_mbps: float) -> None:
            if speed_mbps >= 1000:
                card["value"].set_text(f"{speed_mbps / 1000:.2f}")
                card["unit"].set_text("Gbps")
            else:
                card["value"].set_text(f"{speed_mbps:.1f}")
                card["unit"].set_text("Mbps")

        def _on_backend_changed(self, combo: Adw.ComboRow, _param) -> None:
            if self.running:
                return
            selected = self.backends[combo.get_selected()]
            try:
                # get_backend can raise BackendError from a constructor
                # (e.g. LibreSpeed if LIBRESPEED_URL was unset between
                # available_backends() and now). Surface the error in the
                # status bar; keep the previously-selected backend live.
                self.backend = get_backend(selected)
            except BackendError as e:
                self.status.set_label(
                    f"Cannot select {display_name_for(selected)}: {e}"
                )
                # Roll the dropdown back to the still-active backend.
                combo.handler_block_by_func(self._on_backend_changed)
                combo.set_selected(self.backends.index(self.backend.name))
                combo.handler_unblock_by_func(self._on_backend_changed)
                return
            self.ip_row.set_subtitle("—")
            self.isp_row.set_subtitle("—")
            self.loc_row.set_subtitle("—")
            self.server_row.set_subtitle("—")
            self.status.set_label(f"Backend: {self.backend.display_name}")

        @staticmethod
        def _needs_ookla_enable() -> bool:
            """True when the Ookla backend is in REGISTRY but unavailable —
            i.e. the helper row is worth showing."""
            from backends import REGISTRY
            return "ookla" in REGISTRY and "ookla" not in available_backends()

        def _make_enable_ookla_row(self) -> Adw.ActionRow:
            row = Adw.ActionRow(
                title="Enable Ookla",
                subtitle="Install Ookla's Speedtest CLI to add it to the backend list",
            )
            btn = Gtk.Button(label="Install", css_classes=["suggested-action"],
                             valign=Gtk.Align.CENTER)
            btn.connect("clicked", self._on_install_ookla)
            row.add_suffix(btn)
            row.set_activatable_widget(btn)
            self._ookla_install_btn = btn
            return row

        def _on_install_ookla(self, btn: Gtk.Button) -> None:
            """Kick off `pkexec gui-speedtest-install-ookla` in the background.
            Polkit shows a graphical password prompt; our GUI stays responsive.
            On success we refresh the backend picker; on failure we surface
            the exit code in the status line."""
            import shutil as _shutil
            if not _shutil.which("pkexec"):
                logger.error("Ookla install: pkexec not found on PATH")
                self.status.set_label(
                    "pkexec missing — run 'sudo gui-speedtest-install-ookla' in a terminal"
                )
                return
            logger.info("Ookla install: launching pkexec helper")
            btn.set_sensitive(False)
            btn.set_label("Installing…")
            self.status.set_label("Installing Ookla… (auth prompt)")
            try:
                proc = Gio.Subprocess.new(
                    ["pkexec", "/usr/bin/gui-speedtest-install-ookla"],
                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE,
                )
            except GLib.Error as e:
                logger.error("Ookla install: failed to spawn pkexec: %s", e)
                self.status.set_label(f"Install failed to start: {e}")
                btn.set_sensitive(True)
                btn.set_label("Install")
                return
            proc.communicate_utf8_async(None, None, self._on_ookla_install_done, btn)

        def _on_ookla_install_done(self, proc: Gio.Subprocess, result, btn: Gtk.Button) -> None:
            try:
                _ok, stdout, _stderr = proc.communicate_utf8_finish(result)
            except GLib.Error as e:
                logger.error("Ookla install: communicate failed: %s", e)
                self.status.set_label(f"Install errored: {e}")
                btn.set_sensitive(True)
                btn.set_label("Install")
                return
            rc = proc.get_exit_status()
            logger.info("Ookla install: exit=%s", rc)
            # Trim the installer's stdout to the last few lines for the log.
            for line in (stdout or "").splitlines()[-8:]:
                logger.info("ookla-install: %s", line)
            if rc == 0 and "ookla" in available_backends():
                self.status.set_label("Ookla installed — refreshing backends")
                self._refresh_backend_list()
            else:
                hint = "cancelled" if rc == 126 else f"exit {rc}"
                self.status.set_label(f"Ookla install {hint} — see Log for details")
                btn.set_sensitive(True)
                btn.set_label("Install")

        def _refresh_backend_list(self) -> None:
            """Re-enumerate available backends and rebuild the picker. Called
            after the Ookla installer succeeds so the new backend appears
            without a restart."""
            previous_name = self.backend.name
            new_backends = available_backends()
            logger.info("Refreshing backend list: %s", new_backends)
            self.backends = new_backends
            labels = Gtk.StringList()
            for name in new_backends:
                labels.append(display_name_for(name))
            # Block the change handler so swapping the model doesn't fire
            # _on_backend_changed (which would try to rebuild this all over).
            self.backend_row.handler_block_by_func(self._on_backend_changed)
            self.backend_row.set_model(labels)
            target = previous_name if previous_name in new_backends else new_backends[0]
            self.backend_row.set_selected(new_backends.index(target))
            self.backend_row.handler_unblock_by_func(self._on_backend_changed)
            # Remove the Enable-Ookla row if it's no longer needed.
            if not self._needs_ookla_enable() and self._ookla_row is not None:
                try:
                    self.info_group.remove(self._ookla_row)
                except (ValueError, AttributeError):
                    pass
                self._ookla_row = None

        def _on_close(self, _window) -> bool:
            # Ensure any running subprocess (Ookla) or socket doesn't outlive
            # the window. cancel() is spec'd to not raise; catch OSError in
            # case of process-already-gone races. Return False so close proceeds.
            try:
                self.backend.cancel()
            except OSError:
                pass
            return False

        def _on_show_log(self, _btn: Gtk.Button) -> None:
            log_path = _log_file_path()
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                text = f"(Log file not found yet at {log_path}.\nRun a speed test first.)"
            except OSError as e:
                text = f"(Could not read log file: {e})"

            win = Adw.Window(
                transient_for=self,
                modal=True,
                title="Log",
                default_width=820,
                default_height=620,
            )
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            win.set_content(outer)

            log_header = Adw.HeaderBar()
            log_header.set_title_widget(
                Adw.WindowTitle(title="Log", subtitle=str(log_path))
            )
            # Copy-all button — writes the full text to the system clipboard
            # so users can paste it anywhere without selecting by hand.
            copy_btn = Gtk.Button(label="Copy All", css_classes=["suggested-action"])
            log_header.pack_end(copy_btn)
            # Clear button — truncates the log file so subsequent runs
            # produce a clean trace. Useful when users want to reproduce a
            # specific issue without a pile of irrelevant history.
            clear_btn = Gtk.Button(label="Clear", css_classes=["destructive-action"])
            log_header.pack_end(clear_btn)
            outer.append(log_header)

            scroll = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
            outer.append(scroll)

            buf = Gtk.TextBuffer()
            buf.set_text(text)
            text_view = Gtk.TextView(
                buffer=buf,
                editable=False,
                cursor_visible=False,
                monospace=True,
                wrap_mode=Gtk.WrapMode.WORD_CHAR,
                top_margin=8,
                bottom_margin=8,
                left_margin=12,
                right_margin=12,
            )
            scroll.set_child(text_view)

            def _on_copy(_b: Gtk.Button) -> None:
                clip = win.get_display().get_clipboard()
                clip.set(text)
                copy_btn.set_label("Copied ✓")
                # Reset the label after a moment so the user can click again.
                GLib.timeout_add_seconds(2, lambda: (copy_btn.set_label("Copy All"), False)[1])

            copy_btn.connect("clicked", _on_copy)

            def _on_clear(_b: Gtk.Button) -> None:
                # Truncate the log file in place — the RotatingFileHandler
                # that logged to it keeps writing to the same fd, so new
                # log entries land in the empty file naturally. This also
                # drops any rotated backups (log.1, log.2, ...) to match
                # the user's expectation of a clean slate.
                try:
                    # Drop old rotated files first
                    for sibling in log_path.parent.glob(log_path.name + ".*"):
                        try:
                            sibling.unlink()
                        except OSError as e:
                            logger.debug("clear log: couldn't remove %s: %s", sibling, e)
                    with log_path.open("w", encoding="utf-8"):
                        pass  # truncate to zero bytes
                    logger.info("Log cleared by user")
                    buf.set_text("(Log cleared.)")
                    clear_btn.set_label("Cleared ✓")
                    GLib.timeout_add_seconds(2, lambda: (clear_btn.set_label("Clear"), False)[1])
                except OSError as e:
                    buf.set_text(f"(Could not clear log: {e})")

            clear_btn.connect("clicked", _on_clear)

            win.present()
            # Scroll to the tail so the most recent events are visible first.
            GLib.idle_add(
                lambda: (text_view.scroll_to_iter(buf.get_end_iter(), 0.0, False, 0.0, 0.0), False)[1]
            )

        def _on_start(self, btn: Gtk.Button) -> None:
            # Same button serves as Start / Cancel — label + CSS class tell
            # them apart. If a test is running, this click is Cancel.
            if self.running:
                self._cancel_test()
                return
            self.running = True
            self.cancelled = False
            btn.set_label("Cancel")
            btn.remove_css_class("suggested-action")
            btn.add_css_class("destructive-action")
            self.backend_row.set_sensitive(False)
            self.dl_card["value"].set_text("—")
            self.dl_card["unit"].set_text("Mbps")
            self.ul_card["value"].set_text("—")
            self.ul_card["unit"].set_text("Mbps")
            self.ping_card["value"].set_text("—")
            self.jitter_card["value"].set_text("—")
            # Reset graphs so the previous run doesn't bleed into the new
            # one — users expect Run Again to start from zero.
            self.dl_card["chart"].clear()
            self.ul_card["chart"].clear()
            if "bars" in self.ping_card:
                self.ping_card["bars"].clear()
            for card in (self.dl_card, self.ul_card, self.ping_card, self.jitter_card):
                err = card.get("error")
                if err is not None:
                    err.set_label("")
                    err.set_visible(False)
            self.progress.set_fraction(0)
            threading.Thread(target=self._run_test, daemon=True).start()

        def _cancel_test(self) -> None:
            """Mark the run as cancelled and tell the backend to abort.

            This runs on the GTK main thread (it's a click handler) so
            every UI mutation here is synchronous — no idle_add. Previously
            we queued the status label update, but it got drowned by a
            backlog of pending progress callbacks emitted by the worker
            thread during a slow download (40+ progress events x 3
            idle_adds each). User clicked Cancel and saw "Download 10 MB:
            0.64 Mbps" linger for many seconds instead of immediate
            "Cancelling…" feedback.

            dl_cb / ul_cb / lat_cb short-circuit on self.cancelled so even
            already-queued idle_adds skip their UI updates on arrival.
            """
            logger.info("User clicked Cancel (backend=%s)", self.backend.name)
            self.cancelled = True
            self.status.set_label("Cancelling…")
            self.progress.set_text("Cancelling…")
            self.start_btn.set_sensitive(False)
            try:
                self.backend.cancel()
            except OSError as e:
                logger.debug("_cancel_test: backend.cancel() raised %s", e)

        def _finish_run(self, final_status: str) -> bool:
            """Runs on the main thread at the end of the worker's test loop.
            Scheduled at PRIORITY_HIGH so it preempts any backlog of queued
            status/chart idle_adds — otherwise on a slow link the user
            sees "Cancelling…" for seconds while the queue drains."""
            logger.info("_finish_run: cancelled=%s status=%r", self.cancelled, final_status)
            if self.cancelled:
                self.progress.set_text("Cancelled")
                self.status.set_label("Cancelled")
            else:
                self.progress.set_fraction(1.0)
                self.progress.set_text("Complete")
                self.status.set_label(final_status)
            self.start_btn.set_label("Run Again")
            self.start_btn.remove_css_class("destructive-action")
            self.start_btn.add_css_class("suggested-action")
            self.start_btn.set_sensitive(True)
            self.backend_row.set_sensitive(True)
            self.running = False
            return False  # don't repeat

        def _run_test(self) -> None:
            # Progress bar shows fraction of phases COMPLETED. begin_phase
            # advertises the current phase via text only — the bar stays put
            # until end_phase, so users don't see it leap forward and then
            # sit frozen during the actual slow work.
            phases = ["connect", "latency", "download", "upload"]
            phase_idx = [0]
            logger.info("Run started: backend=%s", self.backend.name)

            def begin_phase(text: str) -> None:
                logger.info("Phase start: %s", phases[phase_idx[0]] if phase_idx[0] < len(phases) else "?")
                GLib.idle_add(self.progress.set_text, text)
                GLib.idle_add(self.status.set_label, text)

            def end_phase() -> None:
                name = phases[phase_idx[0]] if phase_idx[0] < len(phases) else "?"
                phase_idx[0] += 1
                logger.info("Phase end: %s (progress=%.0f%%)", name, phase_idx[0] / len(phases) * 100)
                GLib.idle_add(
                    self.progress.set_fraction, phase_idx[0] / len(phases)
                )

            backend = self.backend
            begin_phase(f"Detecting connection via {backend.display_name}...")
            try:
                info = backend.connection_info()
            except BackendError as e:
                info = None
                GLib.idle_add(
                    self.status.set_label, f"Connection detection failed: {e}"
                )
            if info:
                GLib.idle_add(self.ip_row.set_subtitle, info.ip)
                GLib.idle_add(self.isp_row.set_subtitle, info.isp)
                GLib.idle_add(self.loc_row.set_subtitle, info.location)
                if info.server:
                    GLib.idle_add(self.server_row.set_subtitle, info.server)
            end_phase()
            if self.cancelled:
                GLib.idle_add(self._finish_run, "Cancelled", priority=GLib.PRIORITY_HIGH)
                return

            def lat_cb(event: str, data: dict) -> None:
                if self.cancelled:
                    return
                if event == "latency_sample":
                    GLib.idle_add(
                        self.status.set_label,
                        f"Latency {data['current']}/{data['total']}: "
                        f"{data['value_ms']:.0f} ms",
                    )
                    GLib.idle_add(
                        self.ping_card["value"].set_text, f"{data['value_ms']:.0f}"
                    )
                    # Live ping histogram — one bar per completed sample.
                    if "bars" in self.ping_card:
                        GLib.idle_add(self.ping_card["bars"].add_sample, data["value_ms"])

            begin_phase("Testing latency...")
            try:
                lat = backend.test_latency(samples=latency_samples, callback=lat_cb)
            except BackendError as e:
                lat = None
                lat_text = f"Ping: N/A ({e})"
                GLib.idle_add(self.ping_card["value"].set_text, "N/A")
                GLib.idle_add(self.jitter_card["value"].set_text, "N/A")
                GLib.idle_add(self.ping_card["error"].set_label, str(e))
                GLib.idle_add(self.ping_card["error"].set_visible, True)
            else:
                if lat.failed:
                    lat_text = "Ping: N/A (all samples failed)"
                    GLib.idle_add(self.ping_card["value"].set_text, "N/A")
                    GLib.idle_add(self.jitter_card["value"].set_text, "N/A")
                    GLib.idle_add(self.ping_card["error"].set_label, "all samples failed")
                    GLib.idle_add(self.ping_card["error"].set_visible, True)
                else:
                    lat_text = f"Ping: {lat.avg:.0f} ms"
                    GLib.idle_add(self.ping_card["value"].set_text, f"{lat.avg:.0f}")
                    GLib.idle_add(
                        self.jitter_card["value"].set_text, f"{lat.jitter:.1f}"
                    )
            end_phase()
            if self.cancelled:
                GLib.idle_add(self._finish_run, "Cancelled", priority=GLib.PRIORITY_HIGH)
                return

            def dl_cb(event: str, data: dict) -> None:
                # Drop the callback entirely once the user cancelled —
                # otherwise a backlog of already-in-flight progress events
                # keeps overwriting the "Cancelling…" status with stale
                # mid-chunk speed readings.
                if self.cancelled:
                    return
                # Streaming progress (mid-chunk) and chunk completion both
                # refresh the card so users see continuous motion during a
                # slow download instead of a frozen reading for minutes.
                if event in ("download_chunk", "download_chunk_progress"):
                    GLib.idle_add(
                        self.status.set_label,
                        f"Download {data['label']}: "
                        f"{format_speed(data['speed_mbps'])}",
                    )
                    GLib.idle_add(self._update_speed, self.dl_card, data["speed_mbps"])
                    GLib.idle_add(self.dl_card["chart"].add_sample, data["speed_mbps"])

            begin_phase("Testing download...")
            try:
                download = backend.test_download(callback=dl_cb)
                dl_text = format_speed(download.speed_mbps)
                GLib.idle_add(self._update_speed, self.dl_card, download.speed_mbps)
            except BackendError as e:
                dl_text = "N/A"
                GLib.idle_add(self.dl_card["value"].set_text, "N/A")
                GLib.idle_add(self.dl_card["unit"].set_text, "Mbps")
                GLib.idle_add(self.dl_card["error"].set_label, str(e))
                GLib.idle_add(self.dl_card["error"].set_visible, True)
            end_phase()
            if self.cancelled:
                GLib.idle_add(self._finish_run, "Cancelled", priority=GLib.PRIORITY_HIGH)
                return

            def ul_cb(event: str, data: dict) -> None:
                if self.cancelled:
                    return
                if event in ("upload_chunk", "upload_chunk_progress"):
                    GLib.idle_add(
                        self.status.set_label,
                        f"Upload {data['label']}: "
                        f"{format_speed(data['speed_mbps'])}",
                    )
                    GLib.idle_add(self._update_speed, self.ul_card, data["speed_mbps"])
                    GLib.idle_add(self.ul_card["chart"].add_sample, data["speed_mbps"])

            begin_phase("Testing upload...")
            try:
                upload = backend.test_upload(callback=ul_cb)
                ul_text = format_speed(upload.speed_mbps)
                GLib.idle_add(self._update_speed, self.ul_card, upload.speed_mbps)
            except BackendError as e:
                ul_text = "N/A"
                GLib.idle_add(self.ul_card["value"].set_text, "N/A")
                GLib.idle_add(self.ul_card["unit"].set_text, "Mbps")
                GLib.idle_add(self.ul_card["error"].set_label, str(e))
                GLib.idle_add(self.ul_card["error"].set_visible, True)
            end_phase()

            final = f"Download: {dl_text} | Upload: {ul_text} | {lat_text}"
            # _finish_run flips self.running=False — scheduling via idle_add
            # guarantees it runs AFTER all the progress/label updates above.
            GLib.idle_add(self._finish_run, final, priority=GLib.PRIORITY_HIGH)

    class SpeedTestApp(Adw.Application):
        def __init__(self) -> None:
            super().__init__(application_id=app_id)

        def do_activate(self) -> None:
            SpeedTestWindow(self, backend_name).present()

    SpeedTestApp().run()
