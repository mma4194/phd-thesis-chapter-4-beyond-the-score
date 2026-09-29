# Public feature definitions

The exact selected 64-field view is listed in `reference/toniot/feature_availability.csv` and the four C2ST scopes in `reference/toniot/protocol.json`. Not every decoder diagnostic is a model feature. This dictionary describes preparation; it does not infer a mapping from network endpoints to physical devices.

| Field / family | Definition | Missingness / units |
|---|---|---|
| `packet_count` | Number of complete packet records in the bin, summed across files in one capture group | Count; an unoccupied bin is unobserved |
| `byte_count` and `packet_length_*` | Original wire length, including original length for snaplen-shortened records; min/max/arithmetic mean/population standard deviation | Bytes; variance uses ddof=0 |
| `unique_src_ip_count`, `unique_dst_ip_count` | Distinct outer IP addresses with decoded network headers | Counts; address strings are not model features |
| `unique_endpoint_pair_count` | Distinct directed outer source/destination IP pairs | Count; no transport-port component |
| `ipv4/ipv6/arp/tcp/udp/icmp_count` | Counts according to outer network protocol and decoded next-header chain | Counts; ICMP includes IPv4 and IPv6 variants |
| `tcp_syn/fin/rst_count` | Flag present on decoded TCP headers | Counts; a record can carry multiple flags |
| `http/https/dns/mqtt_port_packets` | Source or destination port in {80}, {443}, {53}, {1883,8883}, respectively | Port heuristic; not a verified application identity |
| `interarrival_positive_mean/std` | Sort all complete timestamps within the same group/bin; retain strictly positive consecutive differences | Seconds; undefined with no positive difference; ddof=0 |
| Fridge temperature / high condition | Mean numeric temperature / mean indicator for high condition | Original numeric coordinate / fraction |
| Garage door / smartphone signal | Fraction open / fraction true | Fractions |
| GPS latitude / longitude | Mean provided numeric reading | Source coordinate; no independently checked location accuracy |
| Modbus registers 1–4 | Mean provided numeric register value | Source register units; no physical-unit inference |
| Motion / light | Fraction true / fraction on | Fractions |
| Thermostat temperature / state | Mean temperature reading / fraction true | Source numeric coordinate / fraction |
| Weather temperature / pressure / humidity | Mean available numeric reading | Source units; no independent calibration |

General capture fields have a `router__general__` prefix; the two IoT-named captures have `router__iot_named__`. Telemetry fields have `iot__<family>__`. Group names describe source filenames, not proven device mappings.

Measurements in filtered records are retained, including duplicate timestamps and repeated values. Original logs check rowwise correspondence and supply the narrowly verified malformed-date correction. Numeric fields use an arithmetic mean of available filtered records in each UTC-coordinate bin. A binary/state field is mapped according to explicit tokens in `tiot_rebuild/telemetry_recovery.py`; unknown tokens become missing. No forward fill, backward fill, interpolation or learned imputation is used in this public preparation.

The packet decoder supports Ethernet (including bounded VLAN stacks), Linux cooked v1/v2 and raw IPv4/IPv6. Noninitial IP fragments contribute protocol counts but not interpreted ports or TCP flags. Malformed header diagnostics are recorded; affected interpreted header-derived features are not certified as complete. Unsupported link types stop decoding. Check the implementation and per-file decoder diagnostics for their exact handling.
