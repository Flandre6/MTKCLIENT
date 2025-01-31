#!/usr/bin/python3
# -*- coding: utf-8 -*-
# (c) B.Kerler 2018-2021 GPLv3 License
import logging
import sys

from mtkclient.Library.utils import LogBase, logsetup
from mtkclient.Library.hwcrypto_gcpu import GCpu
from mtkclient.Library.hwcrypto_dxcc import dxcc
from mtkclient.Library.hwcrypto_sej import sej
from mtkclient.Library.cqdma import cqdma


class crypto_setup:
    hwcode = None
    dxcc_base = None
    gcpu_base = None
    da_payload_addr = None
    sej_base = None
    read32 = None
    write32 = None
    writemem = None
    blacklist = None
    cqdma_base = None
    ap_dma_mem = None
    meid_addr = None
    socid_addr = None
    prov_addr = None
    efuse_base = None


class hwcrypto(metaclass=LogBase):
    def __init__(self, setup, loglevel=logging.INFO, gui: bool = False):
        self.__logger = logsetup(self, self.__logger, loglevel, gui)
        self.info = self.__logger.info
        self.error = self.__logger.error
        self.warning = self.__logger.warning
        self.dxcc = dxcc(setup, loglevel, gui)
        self.gcpu = GCpu(setup, loglevel, gui)
        self.sej = sej(setup, loglevel)
        self.cqdma = cqdma(setup, loglevel)
        self.hwcode = setup.hwcode
        self.setup = setup
        self.read32 = setup.read32
        self.write32 = setup.write32
        self.meid_addr = setup.meid_addr
        self.socid_addr = setup.socid_addr
        self.prov_addr = setup.prov_addr

    def mtee(self, data, keyseed, ivseed, aeskey1, aeskey2):
        self.gcpu.init()
        self.gcpu.acquire()
        return self.gcpu.mtk_gcpu_decrypt_mtee_img(data, keyseed, ivseed, aeskey1, aeskey2)

    def aes_hwcrypt(self, data=b"", iv=None, encrypt=True, otp=None, mode="cbc", btype="sej"):
        if otp is None:
            otp = 32 * b"\00"
        else:
            if isinstance(otp, str):
                otp = bytes.fromhex(otp)
        if btype == "sej":
            if encrypt:
                if mode == "cbc":
                    return self.sej.hw_aes128_cbc_encrypt(buf=data, encrypt=True)
                elif mode == "sst":
                    data2=self.sej.generate_hw_meta(encrypt=True,data=data)
                    data3=self.sej.SST_Secure_Algo_With_Level(buf=data, encrypt=True)
                    print(data2.hex())
                    print(data3.hex())
                    sys.stdout.flush()
                    return data3
            else:
                if mode == "cbc":
                    return self.sej.hw_aes128_cbc_encrypt(buf=data, encrypt=False)
                elif mode == "sst":
                    #return self.sej.SST_Secure_Algo_With_Level(buf=data, encrypt=False)
                    data2=self.sej.generate_hw_meta(encrypt=False,data=data)
                    CustomSeed = bytes.fromhex(
                        "00be13bb95e218b53d07a089cb935255294f70d4088f3930350bc636cc49c9025ece7a62c292853ef55b23a6ef7b7464c7f3f2a74ae919416d6b4d9c1d6809655dd82d43d65999cf041a386e1c0f1e58849d8ed09ef07e6a9f0d7d3b8dad6cbae4668a2fd53776c3d26f88b0bf617c8112b8b1a871d322d9513491e07396e1638090055f4b8b9aa2f4ec24ebaeb917e81f468783ea771b278614cd5779a3ca50df5cc5af0edc332e2b69b2b42154bcfffd0af13ce5a467abb7fb107fe794f928da44b6db7215aa53bd0398e3403126fad1f7de2a56edfe474c5a06f8dd9bc0b3422c45a9a132e64e48fcacf63f787560c4c89701d7c125118c20a5ee820c3a16")
                    seed = (CustomSeed[2] << 16) | (CustomSeed[1] << 8) | CustomSeed[0] | (CustomSeed[3] << 24)
                    iv = [seed, (~seed) & 0xFFFFFFFF, (((seed >> 16) | (seed << 16)) & 0xFFFFFFFF),
                          (~((seed >> 16) | (seed << 16)) & 0xFFFFFFFF)]
                    data4=self.sej.hw_aes128_cbc_encrypt(buf=data,encrypt=False,iv=iv)
                    data3=self.sej.SST_Secure_Algo_With_Level(buf=data, encrypt=False)
                    print(data2.hex())
                    print(data3.hex())
                    sys.stdout.flush()
            if mode == "rpmb":
                return self.sej.generate_rpmb(meid=data, otp=otp)
            elif mode == "mtee":
                return self.sej.generate_mtee(otp=otp)
            elif mode == "mtee3":
                return self.sej.generate_mtee_hw(otp=otp)
        elif btype == "gcpu":
            addr = self.setup.da_payload_addr
            if mode == "ecb":
                return self.gcpu.aes_read_ecb(data=data, encrypt=encrypt)
            elif mode == "cbc":
                if self.gcpu.aes_setup_cbc(addr=addr, data=data, iv=iv, encrypt=encrypt):
                    return self.gcpu.aes_read_cbc(addr=addr, encrypt=encrypt)
            elif mode == "mtee":
                if self.hwcode in [0x321]:
                    return self.gcpu.mtk_gcpu_mtee_6735()
                elif self.hwcode in [0x8167,0x8163,0x8176]:
                    return self.gcpu.mtk_gcpu_mtee_8167()
        elif btype == "dxcc":
            if mode == "fde":
                return self.dxcc.generate_rpmb(1)
            elif mode == "rpmb2":
                return self.dxcc.generate_rpmb(2)
            elif mode == "rpmb":
                return self.dxcc.generate_rpmb()
            elif mode == "mirpmb":
                return self.dxcc.generate_rpmb_mitee()
            elif mode == "itrustee":
                return self.dxcc.generate_itrustee_fbe()
            elif mode == "prov":
                return self.dxcc.generate_provision_key()
            elif mode == "sha256":
                return self.dxcc.generate_sha256(data=data)
        else:
            self.error("Unknown aes_hwcrypt type: " + btype)
            self.error("aes_hwcrypt supported types are: sej")
            return bytearray()

    def orval(self, addr, value):
        self.write32(addr, self.read32(addr) | value)

    def andval(self, addr, value):
        self.write32(addr, self.read32(addr) & value)

    def disable_hypervisor(self):
        self.write32(0x1021a060, self.read32(0x1021a060) | 0x1)

    def disable_range_blacklist(self, btype, refreshcache):
        if btype == "gcpu":
            self.info("GCPU Init Crypto Engine")
            self.gcpu.init()
            self.gcpu.acquire()
            self.gcpu.init()
            self.gcpu.acquire()
            self.info("Disable Caches")
            refreshcache(b"\xB1")
            self.info("GCPU Disable Range Blacklist")
            self.gcpu.disable_range_blacklist()
        elif btype == "cqdma":
            self.info("Disable Caches")
            refreshcache(b"\xB1")
            self.info("CQDMA Disable Range Blacklist")
            self.cqdma.disable_range_blacklist()
