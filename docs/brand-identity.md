# ODIN Assistant — Brand identity

## Primary mark

The primary brand mark is **Ø**: a circular ring crossed by a diagonal spear stroke.
Use the same proportions and direction across desktop, Android launcher, notification,
splash, About, and documentation artwork.

## Color system

- Brand field: deep ink (#101013, with a subtle dark vertical gradient only in app icons).
- Mark: near-white (#F2F5F9).
- Brand tint: neutral light gray (#EDEDF0).
- Green, red, and amber remain semantic UI colors for trading direction, veto/status,
  and ranking. They are not logo colors.
- Aurora indigo/cyan/pink remain low-opacity ambient background effects; they are not
  part of the primary logo or brand accent.

## Asset ownership

- assets/make_icon.py generates desktop assets/icon.png and assets/icon.ico.
- docs/odin-launcher-icon.svg is the scalable reference artwork.
- Android launcher and status-bar icons are native vector drawables.
- Android splash and About use inline SVG with the same mark geometry.
- Desktop splash uses the logo glyph in src/ui/icons.py.

## Change control

When the mark geometry or brand tokens change, update every asset above and run:

    node tests/js/smoke_brand_identity.js
    node tests/js/smoke_theme_parity.js
    python assets/make_icon.py
