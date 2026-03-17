"""Tests for app/core/device.py — pure logic only (no network/socket calls)."""

import pytest
from app.core.device import SessantaquattroPlus


@pytest.fixture
def device():
    return SessantaquattroPlus()


class TestGetNumChannels:
    """get_num_channels maps (NCH, MODE) to channel count."""

    @pytest.mark.parametrize("nch,mode,expected", [
        (0, 0, 16),
        (0, 1, 12),
        (1, 0, 24),
        (1, 1, 16),
        (2, 0, 40),
        (2, 1, 24),
        (3, 0, 72),
        (3, 1, 40),
    ])
    def test_channel_counts(self, device, nch, mode, expected):
        assert device.get_num_channels(nch, mode) == expected

    def test_unknown_nch_returns_72(self, device):
        assert device.get_num_channels(99, 0) == 72


class TestGetSamplingFrequency:
    """get_sampling_frequency maps (FSAMP, MODE) to Hz."""

    @pytest.mark.parametrize("fsamp,mode,expected", [
        (0, 0, 500),
        (1, 0, 1000),
        (2, 0, 2000),
        (3, 0, 4000),
        (0, 3, 2000),
        (1, 3, 4000),
        (2, 3, 8000),
        (3, 3, 16000),
    ])
    def test_sampling_frequencies(self, device, fsamp, mode, expected):
        assert device.get_sampling_frequency(fsamp, mode) == expected

    def test_unknown_fsamp_returns_2000(self, device):
        assert device.get_sampling_frequency(99, 0) == 2000


class TestCreateCommand:
    """create_command assembles a 16-bit command word from individual bit fields."""

    def test_go_bit_is_bit_0(self, device):
        # GO=1 with everything else 0 → Command = 1
        cmd = device.create_command(FSAMP=0, NCH=0, MODE=0, HRES=0, HPF=0,
                                    EXTEN=0, TRIG=0, REC=0, GO=1)
        assert cmd & 0x1 == 1

    def test_stop_command_go_0(self, device):
        cmd = device.create_command(FSAMP=0, NCH=0, MODE=0, HRES=0, HPF=0,
                                    EXTEN=0, TRIG=0, REC=0, GO=0)
        assert cmd == 0

    def test_rec_bit_is_bit_1(self, device):
        cmd = device.create_command(FSAMP=0, NCH=0, MODE=0, HRES=0, HPF=0,
                                    EXTEN=0, TRIG=0, REC=1, GO=0)
        assert cmd == (1 << 1)

    def test_hpf_bit_is_bit_6(self, device):
        cmd = device.create_command(FSAMP=0, NCH=0, MODE=0, HRES=0, HPF=1,
                                    EXTEN=0, TRIG=0, REC=0, GO=0)
        assert cmd == (1 << 6)

    def test_hres_bit_is_bit_7(self, device):
        cmd = device.create_command(FSAMP=0, NCH=0, MODE=0, HRES=1, HPF=0,
                                    EXTEN=0, TRIG=0, REC=0, GO=0)
        assert cmd == (1 << 7)

    def test_mode_bits_8_to_10(self, device):
        cmd = device.create_command(FSAMP=0, NCH=0, MODE=1, HRES=0, HPF=0,
                                    EXTEN=0, TRIG=0, REC=0, GO=0)
        assert cmd == (1 << 8)

    def test_nch_bits_11_to_12(self, device):
        cmd = device.create_command(FSAMP=0, NCH=1, MODE=0, HRES=0, HPF=0,
                                    EXTEN=0, TRIG=0, REC=0, GO=0)
        assert cmd == (1 << 11)

    def test_fsamp_bits_13_to_14(self, device):
        cmd = device.create_command(FSAMP=1, NCH=0, MODE=0, HRES=0, HPF=0,
                                    EXTEN=0, TRIG=0, REC=0, GO=0)
        assert cmd == (1 << 13)

    def test_combined_fields(self, device):
        # GO=1, HPF=1, NCH=3, FSAMP=2 — the typical default combination.
        expected = 1 + (1 << 6) + (3 << 11) + (2 << 13)
        cmd = device.create_command(FSAMP=2, NCH=3, MODE=0, HRES=0, HPF=1,
                                    EXTEN=0, TRIG=0, REC=0, GO=1)
        assert cmd == expected

    def test_create_command_sets_nchannels(self, device):
        device.create_command(FSAMP=0, NCH=3, MODE=0, HRES=0, HPF=0,
                               EXTEN=0, TRIG=0, REC=0, GO=1)
        assert device.nchannels == 72  # NCH=3, MODE=0 → 72

    def test_create_command_sets_frequency(self, device):
        device.create_command(FSAMP=2, NCH=0, MODE=0, HRES=0, HPF=0,
                               EXTEN=0, TRIG=0, REC=0, GO=1)
        assert device.frequency == 2000  # FSAMP=2, MODE=0 → 2000 Hz
