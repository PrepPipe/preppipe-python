# -*- coding: utf-8 -*-

import os

from PIL import Image

from fgui_converter.FguiAssetsParseLib import FguiBitmapFont, FguiBitmapFontChar, FguiPackage, FguiSpriteInfo


class _BmFontCharEntry:
    def __init__(self, char_id : int, x : int, y : int, width : int, height : int,
                 xoffset : int, yoffset : int, xadvance : int, chnl : int):
        self.char_id = char_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.xadvance = xadvance
        self.chnl = chnl


class BmFontGenerator:
    """
    将 FairyGUI 位图字体描述转换为 Ren'Py 可用的 AngelCode BMFont 文本格式，
    并从 FairyGUI 图集中重新生成字体纹理。
    """
    SPACE_CHAR_ID = 32

    @staticmethod
    def _resolve_default_chnl(font : FguiBitmapFont) -> int:
        return 15

    @staticmethod
    def _ensure_renpy_required_chars(font : FguiBitmapFont, entries : list[_BmFontCharEntry],
                                     scale_w : int, scale_h : int) -> tuple[list[_BmFontCharEntry], int, int]:
        """Ren'Py 加载 BMFont 时需要空格字符 (id=32)。"""
        if any(entry.char_id == BmFontGenerator.SPACE_CHAR_ID for entry in entries):
            return entries, scale_w, scale_h
        space_xadvance = font.xadvance or max(1, font.size // 2)
        chnl = BmFontGenerator._resolve_default_chnl(font)
        entries.append(_BmFontCharEntry(
            BmFontGenerator.SPACE_CHAR_ID, scale_w, 0, 1, 1,
            0, 0, space_xadvance, chnl,
        ))
        return entries, scale_w + 1, scale_h

    @staticmethod
    def _get_sprite(image_id : str, sprites : list[FguiSpriteInfo]) -> FguiSpriteInfo | None:
        for sprite in sprites:
            if sprite.image_id == image_id:
                return sprite
        return None

    @staticmethod
    def _is_image_based_font(font : FguiBitmapFont) -> bool:
        return any(char.image_id for char in font.chars)

    @staticmethod
    def _resolve_xadvance(font : FguiBitmapFont, char : FguiBitmapFontChar, width : int) -> int:
        if char.xadvance:
            return char.xadvance
        if font.xadvance:
            return font.xadvance
        return width

    @staticmethod
    def _resolve_chnl(font : FguiBitmapFont, char : FguiBitmapFontChar) -> int:
        if char.chnl is not None:
            return char.chnl
        return 15

    @staticmethod
    def _get_atlas_key(sprite : FguiSpriteInfo) -> str:
        if sprite.atlas_index == -1:
            return f'atlas_{sprite.image_id}'
        return f'atlas{sprite.atlas_index}'

    @staticmethod
    def _load_atlas_image(atlas_source_dir : str, atlas_dicts : dict[str, str],
                          atlas_key : str, atlas_cache : dict[str, Image.Image]) -> Image.Image:
        if atlas_key not in atlas_cache:
            atlas_file = atlas_dicts.get(atlas_key)
            if not atlas_file:
                raise ValueError(f'Could not find atlas mapping for {atlas_key}.')
            atlas_path = os.path.join(atlas_source_dir, atlas_file)
            if not os.path.exists(atlas_path):
                raise FileNotFoundError(f'Could not find atlas file: {atlas_path}')
            atlas_cache[atlas_key] = Image.open(atlas_path).convert('RGBA')
        return atlas_cache[atlas_key]

    @staticmethod
    def _compute_atlas_scale_size(package_size : tuple[int, int],
                                  entries : list[_BmFontCharEntry]) -> tuple[int, int]:
        content_w = max((entry.x + entry.width for entry in entries), default=0)
        content_h = max((entry.y + entry.height for entry in entries), default=0)
        return max(package_size[0], content_w), max(package_size[1], content_h)

    @staticmethod
    def _crop_font_texture_from_atlas(atlas_image : Image.Image, sprite : FguiSpriteInfo,
                                      scale_w : int, scale_h : int) -> Image.Image:
        if sprite.rotate:
            raise ValueError(f'Rotated sprite {sprite.image_id} is not supported for bitmap font texture generation.')
        atlas_w, atlas_h = atlas_image.size
        crop_w = min(scale_w, atlas_w - sprite.x)
        crop_h = min(scale_h, atlas_h - sprite.y)
        if crop_w <= 0 or crop_h <= 0:
            raise ValueError(
                f'Font texture crop for {sprite.image_id} is outside atlas bounds: '
                f'({sprite.x}, {sprite.y}, {scale_w}, {scale_h}) in {atlas_w}x{atlas_h}.')
        texture = atlas_image.crop((sprite.x, sprite.y, sprite.x + crop_w, sprite.y + crop_h))
        if texture.size != (scale_w, scale_h):
            canvas = Image.new('RGBA', (scale_w, scale_h), (0, 0, 0, 0))
            canvas.paste(texture, (0, 0))
            texture = canvas
        return texture

    @staticmethod
    def _crop_sprite_from_atlas(atlas_image : Image.Image, sprite : FguiSpriteInfo) -> Image.Image:
        if sprite.rotate:
            raise ValueError(f'Rotated sprite {sprite.image_id} is not supported for bitmap font texture generation.')
        box = (sprite.x, sprite.y, sprite.x + sprite.width, sprite.y + sprite.height)
        return atlas_image.crop(box)

    @staticmethod
    def _build_char_entries(font : FguiBitmapFont, package_desc : FguiPackage,
                            sprites : list[FguiSpriteInfo]) -> tuple[list[_BmFontCharEntry], int, int]:
        if BmFontGenerator._is_image_based_font(font):
            entries, scale_w, scale_h = BmFontGenerator._build_image_based_entries(font, sprites)
        else:
            entries, scale_w, scale_h = BmFontGenerator._build_atlas_based_entries(font, package_desc)
        return BmFontGenerator._ensure_renpy_required_chars(font, entries, scale_w, scale_h)

    @staticmethod
    def _build_image_based_entries(font : FguiBitmapFont,
                                   sprites : list[FguiSpriteInfo]) -> tuple[list[_BmFontCharEntry], int, int]:
        entries = []
        cursor_x = 0
        max_height = 0
        spacing = 1
        for char in font.chars:
            if not char.image_id:
                raise ValueError(f'Bitmap font {font.name} is missing image_id for character {char.char_id}.')
            sprite = BmFontGenerator._get_sprite(char.image_id, sprites)
            if sprite is None:
                raise ValueError(f'Could not find sprite info for image {char.image_id} in font {font.name}.')
            width = sprite.width
            height = sprite.height
            max_height = max(max_height, height)
            xadvance = BmFontGenerator._resolve_xadvance(font, char, width)
            entries.append(_BmFontCharEntry(
                char.char_id, cursor_x, 0, width, height,
                char.xoffset, char.yoffset, xadvance,
                BmFontGenerator._resolve_chnl(font, char),
            ))
            cursor_x += width + spacing
        scale_w = max(cursor_x - spacing, 0)
        scale_h = max_height
        return entries, scale_w, scale_h

    @staticmethod
    def _build_atlas_based_entries(font : FguiBitmapFont,
                                   package_desc : FguiPackage) -> tuple[list[_BmFontCharEntry], int, int]:
        texture_image = package_desc.get_image_by_id(font.texture) if font.texture else None
        if texture_image is None and font.font_texture:
            texture_image = package_desc.get_image_by_id(font.font_texture)
        if texture_image is None:
            raise ValueError(f'Could not find texture image for bitmap font {font.name}.')
        entries = []
        for char in font.chars:
            if char.x is None or char.y is None or char.width is None or char.height is None:
                raise ValueError(f'Bitmap font {font.name} is missing atlas char metrics for character {char.char_id}.')
            xadvance = BmFontGenerator._resolve_xadvance(font, char, char.width)
            entries.append(_BmFontCharEntry(
                char.char_id, char.x, char.y, char.width, char.height,
                char.xoffset, char.yoffset, xadvance,
                BmFontGenerator._resolve_chnl(font, char),
            ))
        scale_w, scale_h = BmFontGenerator._compute_atlas_scale_size(texture_image.size, entries)
        return entries, scale_w, scale_h

    @staticmethod
    def generate_texture(font : FguiBitmapFont, package_desc : FguiPackage,
                         sprites : list[FguiSpriteInfo], atlas_source_dir : str,
                         atlas_dicts : dict[str, str]) -> Image.Image:
        entries, scale_w, scale_h = BmFontGenerator._build_char_entries(font, package_desc, sprites)
        atlas_cache : dict[str, Image.Image] = {}
        if BmFontGenerator._is_image_based_font(font):
            char_by_id = {char.char_id: char for char in font.chars}
            texture = Image.new('RGBA', (scale_w, scale_h), (0, 0, 0, 0))
            for entry in entries:
                char = char_by_id.get(entry.char_id)
                if char is None:
                    continue
                sprite = BmFontGenerator._get_sprite(char.image_id, sprites)
                atlas_key = BmFontGenerator._get_atlas_key(sprite)
                atlas_image = BmFontGenerator._load_atlas_image(
                    atlas_source_dir, atlas_dicts, atlas_key, atlas_cache)
                glyph = BmFontGenerator._crop_sprite_from_atlas(atlas_image, sprite)
                texture.paste(glyph, (entry.x, entry.y), glyph)
            return texture

        texture_id = font.texture or font.font_texture
        sprite = BmFontGenerator._get_sprite(texture_id, sprites)
        if sprite is None:
            raise ValueError(f'Could not find sprite info for font texture {texture_id} in font {font.name}.')
        atlas_key = BmFontGenerator._get_atlas_key(sprite)
        atlas_image = BmFontGenerator._load_atlas_image(
            atlas_source_dir, atlas_dicts, atlas_key, atlas_cache)
        return BmFontGenerator._crop_font_texture_from_atlas(atlas_image, sprite, scale_w, scale_h)

    @staticmethod
    def get_texture_filename(font_name : str) -> str:
        return f'{font_name}_BMfont_texture.png'

    @staticmethod
    def save_texture(font : FguiBitmapFont, package_desc : FguiPackage,
                     sprites : list[FguiSpriteInfo], atlas_source_dir : str,
                     atlas_dicts : dict[str, str], texture_path : str) -> None:
        texture = BmFontGenerator.generate_texture(
            font, package_desc, sprites, atlas_source_dir, atlas_dicts)
        os.makedirs(os.path.dirname(texture_path), exist_ok=True)
        texture.save(texture_path, 'PNG')

    @staticmethod
    def generate(font : FguiBitmapFont, package_desc : FguiPackage,
                 sprites : list[FguiSpriteInfo], page_file : str | None = None) -> str:
        entries, scale_w, scale_h = BmFontGenerator._build_char_entries(font, package_desc, sprites)
        face = font.face or font.name
        line_height = font.line_height or font.size or scale_h
        base = font.base if font.base is not None else line_height
        alpha_chnl = font.alpha_chnl if font.alpha_chnl is not None else (2 if font.colored else 1)
        png_name = page_file or BmFontGenerator.get_texture_filename(font.name)

        lines = [
            f'info face="{face}" size={font.size} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1 outline=0',
            f'common lineHeight={line_height} base={base} scaleW={scale_w} scaleH={scale_h} pages=1 packed=0 alphaChnl={alpha_chnl} redChnl=0 greenChnl=0 blueChnl=0',
            f'page id=0 file="{png_name}"',
            f'chars count={len(entries)}',
        ]
        for entry in entries:
            lines.append(
                f'char id={entry.char_id:<5} x={entry.x:<5} y={entry.y:<5} '
                f'width={entry.width:<5} height={entry.height:<5} '
                f'xoffset={entry.xoffset:<5} yoffset={entry.yoffset:<5} '
                f'xadvance={entry.xadvance:<5} page=0  chnl={entry.chnl}'
            )
        return '\n'.join(lines) + '\n'
