def build_raw_avcC(codec_private_data):
    """
    Build raw avcC box (without the 8-byte header).
    :param codec_private_data: A bytes object containing the codec private data.
    :return: A tuple (avcC_box, box_size) where avcC_box is the constructed box as a bytearray,
             and box_size is the size of the box.
    """
    assert codec_private_data[0] == 0
    assert codec_private_data[1] == 0
    assert codec_private_data[2] == 0
    assert codec_private_data[3] == 1

    mark = 0x00000001
    length = len(codec_private_data) + 3
    avcC = bytearray(length)

    # Extract SPS
    sps_start = 4  # Skip the initial 4 bytes
    candidate = ~mark & 0xFFFFFFFF
    sps_len = 0

    for i in range(sps_start, len(codec_private_data)):
        avcC[8 + i - sps_start] = codec_private_data[i]
        candidate = ((candidate << 8) | codec_private_data[i]) & 0xFFFFFFFF
        if candidate == mark:
            sps_len = i - sps_start - 3
            break

    if sps_len == 0:
        return None, 0

    # Extract PPS
    pps_start = sps_start + sps_len + 4
    pps_len = len(codec_private_data) - pps_start
    avcC[8 + sps_len + 3:8 + sps_len + 3 + pps_len] = codec_private_data[pps_start:pps_start + pps_len]

    # Constants
    AVCProfileIndication = 0x64
    profile_compatibility = 0x40
    AVCLevelIndication = 0x1F
    lengthSizeMinusOne = 0x03

    # Write AVC configuration
    avcC[0] = 1
    avcC[1] = AVCProfileIndication
    avcC[2] = profile_compatibility
    avcC[3] = AVCLevelIndication
    avcC[4] = 0xFC | lengthSizeMinusOne
    avcC[5] = 0xE0 | 1
    avcC[6] = (sps_len >> 8) & 0xFF
    avcC[7] = sps_len & 0xFF
    avcC[8 + sps_len] = 1
    avcC[9 + sps_len] = (pps_len >> 8) & 0xFF
    avcC[10 + sps_len] = pps_len & 0xFF

    return avcC, length


def hex_to_bytes(hex_string):
    """
    Converts a hexadecimal string to a bytes object.

    :param hex_string: A string representing hexadecimal values (e.g., "4a6f686e").
    :return: A bytes object.
    """
    if len(hex_string) % 2 != 0:
        raise ValueError("Hex string must have an even number of characters.")
    return bytes.fromhex(hex_string)



codec_private_data = hex_to_bytes("0000000140010C01FFFF01600000030090000003000003009695980900000001420101016000000300900000030000030096A001E020021C596566924C2F016A02020208000003000800000300C840000000014401C172B66240")
avcC_box, box_size = build_raw_avcC(codec_private_data)
print("Box Size -", box_size)
print("AVC Box -", avcC_box)
#with open("init.mp4", "wb") as file:
    #file.write(avcC_box)