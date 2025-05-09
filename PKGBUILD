# Maintainer: cousteauche <your.email@example.com>
pkgname=omen-rgb-gui
_gitname=${pkgname} # Assumes repo name matches pkgname
pkgver=0.1.r0.gDEADBEEF # Placeholder, will be overwritten by pkgver()
pkgrel=1
pkgdesc="PyQt6 GUI for HP Omen 4-zone keyboard RGB control"
arch=('any')
url="https://github.com/cousteauche/omen-rgb-gui"
source=("$pkgname::git+$url.git#branch=PKGBUILD")
license=('GPL3') # Ensure you have a LICENSE file in your repo
depends=(
    'python-pyqt6'
    'polkit'
    # Optional: 'hp-wmi-omen-rgb-dkms' (or similar kernel module package)
)
makedepends=('git')
source=("git+${url}.git")
sha256sums=('SKIP')

pkgver() {
  cd "${srcdir}/${_gitname}"
  git describe --long --tags --dirty --abbrev=7 2>/dev/null | \
    sed -E 's/^v//; s/-([0-9]+)-g([0-9a-fA-F]+)/.r\1.\2/; s/-/./g; s/\.dirty$/.dirty/' || \
    printf "0.r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short=7 HEAD)"
}

package() {
  cd "${srcdir}/${_gitname}"

  # GUI script
  install -Dm755 "omen-rgb-gui.py" "${pkgdir}/usr/bin/${pkgname}"

  # Helper script
  install -Dm755 "helper/omen-rgb-helper.sh" "${pkgdir}/usr/bin/omen-rgb-helper.sh"

  # Polkit policy
  # IMPORTANT: Ensure policy/com.github.cousteauche.omenrgbgui.policy
  #            points to /usr/bin/omen-rgb-helper.sh
  install -Dm644 "policy/com.github.cousteauche.omenrgbgui.policy" \
    "${pkgdir}/usr/share/polkit-1/actions/com.github.cousteauche.omenrgbgui.policy"

  # (Optional) Desktop entry and icon
  install -Dm644 "path/to/your.desktop" "${pkgdir}/usr/share/applications/${pkgname}.desktop"
  install -Dm644 "path/to/your/icon.png" "${pkgdir}/usr/share/pixmaps/${pkgname}.png"

  # Documentation
  #install -Dm644 "README.md" "${pkgdir}/usr/share/doc/${pkgname}/README.md"
  # Make sure you have a LICENSE file at the root of your git repository
  #install -Dm644 "LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
