pkgname=wptoascii
pkgver=1.0.0
pkgrel=1
pkgdesc="ASCII wallpaper generator with GUI"
arch=('any')
depends=('python' 'python-pillow' 'python-pyqt6')
optdepends=('qt6-wayland: native Wayland support')
source=()

package() {
    install -Dm644 "$startdir/wallpaper.py" \
        "$pkgdir/usr/lib/wptoascii/wallpaper.py"

    install -Dm644 "$startdir/wallpaper_gui.py" \
        "$pkgdir/usr/lib/wptoascii/wallpaper_gui.py"

    install -d "$pkgdir/usr/bin"

    cat > "$pkgdir/usr/bin/wptoascii" <<'EOF'
#!/bin/sh
exec /usr/bin/python /usr/lib/wptoascii/wallpaper_gui.py "$@"
EOF

    cat > "$pkgdir/usr/bin/wptoascii-cli" <<'EOF'
#!/bin/sh
exec /usr/bin/python /usr/lib/wptoascii/wallpaper.py "$@"
EOF

    chmod 755 "$pkgdir/usr/bin/wptoascii" \
              "$pkgdir/usr/bin/wptoascii-cli"
}