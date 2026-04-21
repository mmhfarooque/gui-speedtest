import 'package:flutter_test/flutter_test.dart';
import 'package:speedtest_mobile/utils/format_speed.dart';

void main() {
  group('formatSpeed', () {
    test('below 1000 Mbps -> Mbps with 2 decimals', () {
      expect(formatSpeed(42.5), '42.50 Mbps');
      expect(formatSpeed(0), '0.00 Mbps');
      expect(formatSpeed(999.99), '999.99 Mbps');
    });

    test('at or above 1000 Mbps -> Gbps with 2 decimals', () {
      expect(formatSpeed(1000), '1.00 Gbps');
      expect(formatSpeed(2500), '2.50 Gbps');
      expect(formatSpeed(9876.543), '9.88 Gbps');
    });
  });
}
