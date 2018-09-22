# DESCRIPTION
afedrec is a simple recorder for the AFEDRI SDR-Net. It captures the I/Q UDP stream and
saves it into a WAV file suitable for playback in sdr software (HDSDR, SDR-Console, SpectraVue, etc).
LO, timestamp, and sample rate metadata is saved in a Winrad compatible header.

The sdr is automatically located on the network via a broadcast discovery. If there are multiple
SDRs on the network the one which responds first will be used.

Any sample rate can be specified, however it will be automatically adjusted to something that is
compatible with AFEDRI (currently (Aug 2012) ~32k to ~1.3 MSPS). The front end clock (calibrated)
frequency is taken into account during sample rate calculations.
