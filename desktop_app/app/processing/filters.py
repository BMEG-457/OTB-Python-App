from scipy.signal import butter, filtfilt

from app.core.config import Config


def butter_bandpass(data, low, high, fs, order=None):
    if order is None:
        order = Config.FILTER_ORDER
    # filtfilt requires data length > padlen (which is 3*max(len(a), len(b)))
    # For order=4, this needs ~27 samples. Reduce order for small data.
    min_length = 3 * (2 * order + 1)

    if data.shape[-1] < min_length:
        if data.shape[-1] >= Config.FILTER_MIN_SAMPLES:
            order = Config.FILTER_ORDER_SMALL
        else:
            return data

    b, a = butter(order, [low/fs*2, high/fs*2], btype="band")
    return filtfilt(b, a, data)

def notch(data, freq, fs, quality=None):
    if quality is None:
        quality = Config.NOTCH_QUALITY
    if data.shape[-1] < Config.NOTCH_MIN_SAMPLES:
        return data

    b, a = butter(2, [freq/(fs/2)-freq/(fs/2)/quality, freq/(fs/2)+freq/(fs/2)/quality], btype="bandstop")
    return filtfilt(b, a, data)

def rectify(data):
    return abs(data)
