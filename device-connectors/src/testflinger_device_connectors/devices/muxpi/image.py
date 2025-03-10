from enum import Enum


class ImageType(Enum):
    PE = 0
    CE = 1
    PI_DESKTOP = "pi-desktop"
    UBUNTU = "ubuntu"
    CORE = "core"
    CORE20 = "core20"
    UBUNTU_CPC = "ubuntu-cpc"


class PEImageVariant(Enum):
    TEGRA = 0
    KRIA = 1


class Image:
    def __init__(self, image_type: ImageType):
        self.image_type = image_type


class PEImage(Image):
    def __init__(self, variant: PEImageVariant, **kwargs):
        super().__init__(image_type=ImageType.PE, **kwargs)
        self.variant = variant

    def __str__(self):
        return f"PEImage(image_type={self.image_type.name}, "
        "variant={self.variant.name})"

    def __repr__(self):
        return self.__str__()


class CEImage(Image):
    def __init__(self, release: str, **kwargs):
        super().__init__(image_type=ImageType.CE, **kwargs)
        self.release = release

    def __str__(self):
        return f"CEImage(image_type={self.image_type.name}, "
        "release={self.release})"

    def __repr__(self):
        return self.__str__()
