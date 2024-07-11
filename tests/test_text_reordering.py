from mms_ok.fpga import XEM7360


def test_reorder_hex_str():
    src_str = "ABCDEFGH"
    ans_str = "GHEFCDAB"

    for i in range(0, 8):
        assert XEM7360.reorder_hex_str(src_str * i) == (ans_str * i)
