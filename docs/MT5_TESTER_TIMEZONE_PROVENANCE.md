# MT5 Strategy Tester timestamp provenance

Strategy Tester deal times are broker-server wall-clock values. They must not
be relabelled as UTC by appending Z.

For reproducible exports, set InpTesterServerUtcOffsetMinutes to the verified
historical broker server UTC offset for the tested period. The exporter writes
an ISO-8601 timestamp with that explicit offset and records the offset and
timestamp basis in its metadata.

The exporter accepts offsets from -840 to +840 minutes. The default sentinel
99999 is invalid and therefore disables evidence export. This is intentional:
unknown timezone provenance must not enter walk-forward or locked-OOS data.

Keep one offset constant within a test run. Split runs at daylight-saving or
broker-server timezone transitions, and record the evidence source used to
verify the offset. This setting affects tester evidence export only; it does
not change live order execution or broker server time.
