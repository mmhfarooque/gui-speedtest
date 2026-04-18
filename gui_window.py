"""GTK4 + libadwaita window for GUI Speed Test for Linux.

Kept in its own module so the CLI/JSON paths don't pay for GI imports, and
so the window code can evolve without churning the entry-point file.
"""
from __future__ import annotations

import threading

from backends import available_backends, display_name_for, get_backend
from backends.base import BackendError, format_speed


def run_gui(
    backend_name: str, app_name: str, app_id: str, app_version: str, latency_samples: int
) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, GLib, Gtk

    class SpeedTestWindow(Adw.ApplicationWindow):
        def __init__(self, app: Adw.Application, initial_backend: str) -> None:
            super().__init__(application=app, title=app_name)
            # Default size picked to show every control on first open without
            # scrolling: speed cards + latency row + 5 connection rows +
            # progress + status + button + margins ~= 840 px tall.
            self.set_default_size(580, 860)
            # Floor — stops the user accidentally shrinking the window to a
            # state where the cards overlap or the Start button is hidden.
            # ScrolledWindow handles anything taller than this gracefully.
            self.set_size_request(480, 640)
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
            main_box.append(header)

            scroll = Gtk.ScrolledWindow(vexpand=True)
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
                halign=Gtk.Align.CENTER,
            )
            content.append(speed_row)

            self.dl_card = self._make_speed_card("Download")
            self.ul_card = self._make_speed_card("Upload")
            speed_row.append(self.dl_card["frame"])
            speed_row.append(self.ul_card["frame"])

            lat_row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=16,
                halign=Gtk.Align.CENTER,
            )
            content.append(lat_row)

            self.ping_card = self._make_stat_card("Ping")
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
            info_group.add(self.ip_row)
            info_group.add(self.isp_row)
            info_group.add(self.loc_row)
            info_group.add(self.server_row)

            self.progress = Gtk.ProgressBar(show_text=True, margin_top=8)
            self.progress.set_text("Ready")
            content.append(self.progress)

            self.status = Gtk.Label(
                label="Press Start to begin", css_classes=["dim-label"]
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
                """
            )
            Gtk.StyleContext.add_provider_for_display(
                self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        def _make_speed_card(self, label: str) -> dict:
            frame = Gtk.Frame(css_classes=["speed-card"])
            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=4,
                halign=Gtk.Align.CENTER,
            )
            frame.set_child(box)
            box.append(
                Gtk.Label(
                    label=label.upper(), css_classes=["speed-label", "dim-label"]
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
            return {"frame": frame, "value": val, "unit": unit}

        def _make_stat_card(self, label: str) -> dict:
            frame = Gtk.Frame(css_classes=["stat-card"])
            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=2,
                halign=Gtk.Align.CENTER,
            )
            frame.set_child(box)
            box.append(
                Gtk.Label(
                    label=label.upper(), css_classes=["speed-label", "dim-label"]
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
            return {"frame": frame, "value": val, "unit": unit}

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

        def _on_close(self, _window) -> bool:
            # Ensure any running subprocess (Ookla) or socket doesn't outlive
            # the window. cancel() is spec'd to not raise; catch OSError in
            # case of process-already-gone races. Return False so close proceeds.
            try:
                self.backend.cancel()
            except OSError:
                pass
            return False

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
            self.progress.set_fraction(0)
            threading.Thread(target=self._run_test, daemon=True).start()

        def _cancel_test(self) -> None:
            """Mark the run as cancelled and tell the backend to abort.
            For Ookla this kills the subprocess immediately; for HTTP-based
            backends the current chunk finishes (or times out) before the
            thread checks self.cancelled and exits."""
            self.cancelled = True
            try:
                self.backend.cancel()
            except OSError:
                pass
            GLib.idle_add(self.status.set_label, "Cancelling…")
            GLib.idle_add(self.start_btn.set_sensitive, False)

        def _finish_run(self, final_status: str) -> bool:
            """Runs on the main thread after all prior idle_adds have drained —
            this is what releases the `running` flag so there's no window where
            the button is still disabled but self.running is already False."""
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

            def begin_phase(text: str) -> None:
                GLib.idle_add(self.progress.set_text, text)
                GLib.idle_add(self.status.set_label, text)

            def end_phase() -> None:
                phase_idx[0] += 1
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
                GLib.idle_add(self._finish_run, "Cancelled")
                return

            def lat_cb(event: str, data: dict) -> None:
                if event == "latency_sample":
                    GLib.idle_add(
                        self.status.set_label,
                        f"Latency {data['current']}/{data['total']}: "
                        f"{data['value_ms']:.0f} ms",
                    )
                    GLib.idle_add(
                        self.ping_card["value"].set_text, f"{data['value_ms']:.0f}"
                    )

            begin_phase("Testing latency...")
            try:
                lat = backend.test_latency(samples=latency_samples, callback=lat_cb)
            except BackendError as e:
                lat = None
                lat_text = f"Ping: N/A ({e})"
            else:
                if lat.failed:
                    lat_text = "Ping: N/A (all samples failed)"
                    GLib.idle_add(self.ping_card["value"].set_text, "N/A")
                    GLib.idle_add(self.jitter_card["value"].set_text, "N/A")
                else:
                    lat_text = f"Ping: {lat.avg:.0f} ms"
                    GLib.idle_add(self.ping_card["value"].set_text, f"{lat.avg:.0f}")
                    GLib.idle_add(
                        self.jitter_card["value"].set_text, f"{lat.jitter:.1f}"
                    )
            end_phase()
            if self.cancelled:
                GLib.idle_add(self._finish_run, "Cancelled")
                return

            def dl_cb(event: str, data: dict) -> None:
                if event == "download_chunk":
                    GLib.idle_add(
                        self.status.set_label,
                        f"Download {data['label']}: "
                        f"{format_speed(data['speed_mbps'])}",
                    )
                    GLib.idle_add(self._update_speed, self.dl_card, data["speed_mbps"])

            begin_phase("Testing download...")
            try:
                download = backend.test_download(callback=dl_cb)
                dl_text = format_speed(download.speed_mbps)
                GLib.idle_add(self._update_speed, self.dl_card, download.speed_mbps)
            except BackendError as e:
                dl_text = "N/A"
                GLib.idle_add(self.dl_card["value"].set_text, "N/A")
                GLib.idle_add(self.dl_card["unit"].set_text, str(e))
            end_phase()
            if self.cancelled:
                GLib.idle_add(self._finish_run, "Cancelled")
                return

            def ul_cb(event: str, data: dict) -> None:
                if event == "upload_chunk":
                    GLib.idle_add(
                        self.status.set_label,
                        f"Upload {data['label']}: "
                        f"{format_speed(data['speed_mbps'])}",
                    )
                    GLib.idle_add(self._update_speed, self.ul_card, data["speed_mbps"])

            begin_phase("Testing upload...")
            try:
                upload = backend.test_upload(callback=ul_cb)
                ul_text = format_speed(upload.speed_mbps)
                GLib.idle_add(self._update_speed, self.ul_card, upload.speed_mbps)
            except BackendError as e:
                ul_text = "N/A"
                GLib.idle_add(self.ul_card["value"].set_text, "N/A")
                GLib.idle_add(self.ul_card["unit"].set_text, str(e))
            end_phase()

            final = f"Download: {dl_text} | Upload: {ul_text} | {lat_text}"
            # _finish_run flips self.running=False — scheduling via idle_add
            # guarantees it runs AFTER all the progress/label updates above.
            GLib.idle_add(self._finish_run, final)

    class SpeedTestApp(Adw.Application):
        def __init__(self) -> None:
            super().__init__(application_id=app_id)

        def do_activate(self) -> None:
            SpeedTestWindow(self, backend_name).present()

    SpeedTestApp().run()
