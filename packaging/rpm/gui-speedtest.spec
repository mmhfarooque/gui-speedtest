Name:           gui-speedtest
Version:        1.6.11
Release:        1%{?dist}
Summary:        Multi-backend internet speed test with a GTK4 + libadwaita UI

License:        GPL-3.0-or-later
URL:            https://github.com/mmhfarooque/gui-speedtest
# Use the GitHub source tarball for the tagged release.
# fedpkg / copr-cli will fetch and verify the checksum.
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib

# Runtime — the Python GUI bits
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk4
Requires:       libadwaita

# Optional — M-Lab backend; users can dnf-install this separately
Recommends:     python3-websocket-client

# Optional — Ookla Speedtest CLI is shipped by speedtest.net directly, not
# in Fedora repos, so we don't Require it. Users can install via the in-app
# Enable Ookla button or the bundled gui-speedtest-install-ookla helper.

%description
Fast, no-nonsense internet speed test for Linux with a native GTK4 +
libadwaita interface that follows your system light/dark theme.

Four backends behind one picker so you can run against whichever server
you trust most:

  * Cloudflare — global anycast, hits your nearest PoP (default)
  * Ookla Speedtest — wraps the official Ookla CLI
  * M-Lab NDT7 — academic/research-backed, non-commercial
  * LibreSpeed — open-source, configurable self-hosted server

Live sparkline charts for download/upload speeds, per-sample ping
histogram. Command-line + JSON output modes for scripting.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files gui_speedtest backends gui_window

install -Dm0644 data/io.github.mmhfarooque.GuiSpeedTest.desktop \
    %{buildroot}%{_datadir}/applications/io.github.mmhfarooque.GuiSpeedTest.desktop
install -Dm0644 data/icons/io.github.mmhfarooque.GuiSpeedTest.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.mmhfarooque.GuiSpeedTest.svg
install -Dm0644 data/io.github.mmhfarooque.GuiSpeedTest.metainfo.xml \
    %{buildroot}%{_datadir}/metainfo/io.github.mmhfarooque.GuiSpeedTest.metainfo.xml
install -Dm0755 scripts/install-ookla.sh \
    %{buildroot}%{_bindir}/gui-speedtest-install-ookla

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.mmhfarooque.GuiSpeedTest.desktop
appstream-util validate-relax --nonet \
    %{buildroot}%{_datadir}/metainfo/io.github.mmhfarooque.GuiSpeedTest.metainfo.xml

%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/gui-speedtest
%{_bindir}/gui-speedtest-install-ookla
%{_datadir}/applications/io.github.mmhfarooque.GuiSpeedTest.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.mmhfarooque.GuiSpeedTest.svg
%{_datadir}/metainfo/io.github.mmhfarooque.GuiSpeedTest.metainfo.xml

%changelog
* Sun Apr 19 2026 Mahmud Farooque <farooque7@gmail.com> - 1.6.1-1
- Packaging-only bump. Same code as 1.6.0. First release to include .rpm,
  AppImage, Snap, and Flatpak alongside the existing .deb.
* Sun Apr 19 2026 Mahmud Farooque <farooque7@gmail.com> - 1.6.0-1
- Initial RPM packaging.
- Ookla backend live-progress rewrite (jsonl streaming).
- Error text wraps inside cards; no horizontal scrollbar on long errors.
- Run Again now triggers a fresh Ookla CLI invocation.
- Ookla install helper forces IPv4 + hard timeouts.
