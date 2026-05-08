from enum import Enum, auto
import kkdlib
from pathlib import Path
from PIL import Image, ImageFile, ImageOps
from PIL.Image import Transpose
from dataclasses import dataclass, field
from typing import ClassVar

class Compression(Enum):
    BC7 = "BC7"
    ATI2 = "YCbCr"
    DXT5 = "DXT5"
    RGBA = "Uncompressed"

    def __str__(self):
        return f"{self.value}"

    def to_kkdlib_format(self):
        match self:
            case Compression.ATI2:
               return kkdlib.txp.Format.BC5
            case Compression.DXT5:
                return kkdlib.txp.Format.BC3
            case Compression.BC7:
                return kkdlib.txp.Format.BC7
            case Compression.RGBA:
                return kkdlib.txp.Format.RGBA8

    def default_spr_name(self):
        match self:
            case Compression.ATI2:
               return "MERGE_BC5COMP"
            case Compression.DXT5:
                return "MERGE_D5COMP"
            case Compression.BC7:
                return "MERGE_BC7COMP"
            case Compression.RGBA:
                return "MERGE_NOCOMP"

@dataclass
class txp_info:
    _id_count: ClassVar[int] = 0
    id: int = field(init=False)
    data: Image.Image
    width: float = field(init=False)
    height: float = field(init=False)

    def __post_init__(self):
        self.id = self._id_count
        type(self)._id_count += 1
        self.width = self.data.width
        self.height = self.data.height

@dataclass
class spr_info:
    texture_id: int
    start_x: float
    start_y: float
    width: float
    height: float

class Farc:
    def __init__(self, compression=Compression.RGBA):
        txp_info._id_count = 0
        self.compression = compression
        self.texture_dict = {}
        self.sprit_dict = {}

    def add_texture(self, data):
        info = txp_info(data)
        name = f"{self.compression.default_spr_name()}_{info.id}"
        self.texture_dict.update({name: info})
        return info.id

    def add_sprite(self, name, setting):
        info = spr_info(*setting)
        self.sprit_dict.update({name: info})

    def _get_texture_index(self, _name):
        for name, info in self.texture_dict.items():
            if name == _name:
                return info.id
        return -1

    def _convert_to_texture(self, info):
        if self.compression is Compression.ATI2:
            if hasattr(kkdlib.txp.Texture, "py_ycbcr_from_rgba_gpu"):
                return kkdlib.txp.Texture.py_ycbcr_from_rgba_gpu(info.width, info.height, info.data.tobytes())
            else:
                return kkdlib.txp.Texture.encode_ycbcr(info.width, info.height, info.data.tobytes())
        else:
            if hasattr(kkdlib.txp.Texture, "py_from_rgba_gpu"):
                return kkdlib.txp.Texture.py_from_rgba_gpu(info.width, info.height, info.data.tobytes(), self.compression.to_kkdlib_format())
            else:
                return kkdlib.txp.Texture.py_from_rgba(info.width, info.height, info.data.tobytes(), self.compression.to_kkdlib_format())

    def export_farc(self, export_name, export_path, aft_mode=False):
        txp = kkdlib.txp.Set()
        name_list = []
        for name, info in self.texture_dict.items():
            name_list.append(name)
            txp.add_file(self._convert_to_texture(info))

        spr_bin = kkdlib.spr.Set()
        spr_bin.set_txp(txp, name_list)
        spr_bin.ready = True

        for name, txp_info in self.sprit_dict.items():
            info = kkdlib.spr.Info()
            info.texid = txp_info.texture_id
            info.resolution_mode = kkdlib.spr.ResolutionMode.HD if aft_mode else kkdlib.spr.ResolutionMode.FHD
            info.px = txp_info.start_x
            info.py = txp_info.start_y
            info.width = txp_info.width
            info.height = txp_info.height
            spr_bin.add_spr(info, name)

        farc = kkdlib.farc.Farc()
        farc.add_file_data(f"{export_name}.bin", spr_bin.to_buf())
        farc.write(str(export_path.joinpath(f"{export_name}.farc")), False, False)

def fit_image(img, width, height, alpha_edge=False):
    import numpy as np
    img = ImageOps.fit(img, (width, height), Image.Resampling.LANCZOS)
    img_array = np.array(img)
    expand_data = np.pad(img_array, pad_width=((2,2),(2,2),(0,0)), mode='edge')
    if alpha_edge:
        alpha_img = Image.fromarray(expand_data)
        alpha_img.putalpha(0)
        img = img.crop((1, 1, img.size[0]-1, img.size[0]-1))
        alpha_img.paste(img, (3, 3))
        return alpha_img
    else:
        return Image.fromarray(expand_data)

def create_sel_texture_0(bg_path, jk_path=None):
    img_data = Image.new("RGBA", (2048, 1024))
    if not jk_path:
        jk_path = bg_path
    bg_img = fit_image(Image.open(bg_path), 1280, 720)
    jk_img = fit_image(Image.open(jk_path), 502, 502, True)
    img_data.paste(bg_img, (0, 0))
    img_data.paste(jk_img, (1284, 0))
    return img_data.transpose(Transpose.FLIP_TOP_BOTTOM)

def create_sel_texture_1(logo_path):
    img_data = Image.new("RGBA", (1024, 512))
    if logo_path:
        logo_img = ImageOps.pad(Image.open(logo_path).convert("RGBA"), (870, 330))
        img_data.paste(logo_img)
    return img_data.transpose(Transpose.FLIP_TOP_BOTTOM)

def create_spr_sel_farc(pv_id, spr_path_dict, export_path, compression=Compression.ATI2):
    farc = Farc(compression)
    texture_0 = create_sel_texture_0(spr_path_dict.pop("bg_path"), spr_path_dict.pop("jk_path"))
    texture_1 = create_sel_texture_1(spr_path_dict.pop("logo_path", None))
    bg_jk_index = farc.add_texture(texture_0)
    logo_index  = farc.add_texture(texture_1)
    farc.add_sprite(f"SONG_BG{pv_id:03d}", setting=(bg_jk_index, 2, 2, 1280, 720))
    farc.add_sprite(f"SONG_JK{pv_id:03d}", setting=(bg_jk_index, 1286, 2, 502, 502))
    farc.add_sprite(f"SONG_LOGO{pv_id:03d}", setting=(logo_index, 2, 2, 870, 330))
    farc.export_farc(f"spr_sel_pv{pv_id:03d}", export_path)
