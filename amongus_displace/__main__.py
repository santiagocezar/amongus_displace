from dataclasses import dataclass
from enum import Enum, Flag, auto
from typing import Iterable, Literal, Optional
from PIL import Image
from importlib.resources import files
from . import assets

amogi_png = files(assets).joinpath("full.png")


Color = int


class Orientation(Enum):

    """
      ######
    ####////
    ########
      ######
      ##  ##
    """

    Vertical = auto()

    """
    ######//##
      ####//##
    ##########
        ####
    """
    Horizontal = auto()

    def rotate(self, pos: tuple[int, int]):
        x, y = pos
        if self == Orientation.Horizontal:
            return y, x
        return x, y


class Flip(Flag):
    Zero = 0
    """
    ######
    ////####    ####
    ########  ##########
    ######    ##//####
    ##  ##    ##//######
    """
    Horizontal = auto()

    """
      ##  ##
      ######      ####
    ########  ##########
    ####////    ####//##
      ######  ######//##
    """
    Vertical = auto()

    """
    ##  ##
    ######    ##//######
    ########  ##//####
    ////####  ##########
    ######      ####
    """
    Both = Horizontal | Vertical

    def flip(self, pos: tuple[int, int]):
        x, y = pos
        if self & Flip.Horizontal:
            x = -x
        if self & Flip.Vertical:
            y = -y

        return (x, y)


@dataclass
class Offset:
    x: int
    y: int
    orientation: Orientation
    flip: Flip

    def transform(self, x: int, y: int):
        x, y = self.orientation.rotate(self.flip.flip((x, y)))

        return x + self.x, y + self.y


@dataclass
class Crewmate:
    offset: Offset
    color: Color


crewmate_pixel_offsets = [
    # -2
    (0, -2),
    (1, -2),
    (2, -2),
    # -1
    (-1, -1),
    (0, -1),
    # 0
    (-1, 0),
    (0, 0),
    (1, 0),
    (2, 0),
    # 1
    (0, 1),
    (1, 1),
    (2, 1),
    # 2
    (0, 2),
    (2, 2),
]
crewmate_border_offsets = [
    # -3
    (0, -3),
    (1, -3),
    (2, -3),
    # -2
    (-1, -2),
    (3, -2),
    # -1
    (-2, -1),
    (3, -1),
    # 0
    (-2, 0),
    (3, 0),
    # 1
    (-1, 1),
    (3, 1),
    # 2
    (-1, 2),
    (1, 2),
    (3, 2),
    # 3
    (0, 3),
    (2, 3),
]

crewmate_mask_offsets = [
    *crewmate_pixel_offsets,
    (1, -1),
    (2, -1),
]


class CheckMongus:
    x = 0
    y = 0
    crewmates = list[Crewmate]()
    orientation: Orientation = Orientation.Horizontal

    current_color: Color = 0

    img: Optional[Image.Image] = None

    def check_visor(self, off: Offset):
        assert self.img

        try:
            visor_a, visor_b = (
                self.img.getpixel(off.transform(1, -1)),
                self.img.getpixel(off.transform(2, -1)),
            )
        except IndexError:
            return False

        return (visor_a == visor_b) and (visor_a != self.current_color)

    def full_crewmate_check(self, off: Offset) -> bool:
        assert self.img

        return all(
            (self.img.getpixel(off.transform(*pixel)) == self.current_color)
            for pixel in crewmate_pixel_offsets
        )

    def check_borders(self, off: Offset) -> bool:
        assert self.img

        different = 0
        difference_tolerance = 0.5

        for pixel in crewmate_border_offsets:
            try:
                pix = self.img.getpixel(off.transform(*pixel))
            except IndexError:
                different += 1
                continue
            if pix != self.current_color:
                different += 1

        return different > (len(crewmate_border_offsets) * difference_tolerance)

    def check_pixels(self, iter: Iterable[tuple[int, int]]):
        assert self.img

        self.current_color = 0
        consecutive = 0

        for x, y in iter:
            # check if it moved into next row/column of pixels
            if (x == 1 and self.orientation == Orientation.Horizontal) or (
                y == 1 and self.orientation == Orientation.Vertical
            ):
                consecutive = 0

            pix = self.img.getpixel((x, y))

            if self.current_color == pix:
                consecutive += 1
            else:
                self.current_color = pix
                consecutive = 0

            # print(pix)
            # if pix[3] == 0:
            #     consecutive = 0

            if consecutive >= 4:
                if self.orientation == Orientation.Vertical:
                    mid_x, mid_y = x, y - 2
                else:
                    mid_x, mid_y = x - 2, y

                # get flip value

                nw, se, ne, sw = (
                    self.img.getpixel((mid_x - 1, mid_y + 1)),
                    self.img.getpixel((mid_x + 1, mid_y - 1)),
                    self.img.getpixel((mid_x - 1, mid_y - 1)),
                    self.img.getpixel((mid_x + 1, mid_y + 1)),
                )

                if ne == sw == self.current_color:
                    #       ## <- northeast
                    # ##########
                    #   ## <- southwest
                    flips = (Flip.Zero, Flip.Both)
                elif nw == se == self.current_color:
                    #   ## <- northwest
                    # ##########
                    #       ## <- southeast
                    flips = (Flip.Horizontal, Flip.Vertical)
                else:
                    continue

                is_amogus = False

                off = Offset(mid_x, mid_y, self.orientation, Flip.Zero)
                for flip in flips:
                    off.flip = flip
                    if (
                        self.check_visor(off)
                        and self.full_crewmate_check(off)
                        and self.check_borders(off)
                    ):
                        is_amogus = True
                        break

                if is_amogus:
                    self.crewmates.append(Crewmate(off, self.current_color))

                self.current_color = 0
                consecutive = 0

    def check(self, image: Image.Image, orientation: Orientation):
        self.img = image
        self.orientation = orientation

        if self.orientation == Orientation.Horizontal:
            self.check_pixels(
                (x, y)
                for y in range(1, self.img.height - 1)
                for x in range(1, self.img.width)
            )
        elif self.orientation == Orientation.Vertical:
            self.check_pixels(
                (x, y)
                for x in range(1, self.img.width - 1)
                for y in range(1, self.img.height)
            )


def main():
    # with open("territorio.png", "rb") as amogi:
    checker = CheckMongus()

    with amogi_png.open("rb") as amogi:
        img = Image.open(amogi)

        checker.check(img, Orientation.Horizontal)
        checker.check(img, Orientation.Vertical)

        found = len(checker.crewmates)

        # for cm in checker.crewmates:
        #     print(cm.offset)
        print(f"found {found} amongi")

        transparent = Image.new("RGBA", img.size, (0, 0, 0, 0))

        mask = Image.new("1", img.size, 0)

        for cm in checker.crewmates:
            for pixel in crewmate_mask_offsets:
                mask.putpixel(cm.offset.transform(*pixel), 1)

        final = Image.composite(img, transparent, mask)
        final.save("amongus.png", "png")

        # for y in range(0, img.height):
        #     for x in range(0, img.width):
        #         pix = img.getpixel((x, y))
        #         newimg.putpixel((x * 3 + 1, y * 3 + 1), pix)

        # newimg.save("overlay.png", "png")


if __name__ == "__main__":
    main()
