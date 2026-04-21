import 'package:flutter_test/flutter_test.dart';
import 'package:speedtest_mobile/models/speed_result.dart';

void main() {
  group('SpeedResult.topHalf', () {
    test('4 samples averages the top 2', () {
      final result = SpeedResult.topHalf([100, 200, 300, 400]);
      expect(result.speedMbps, closeTo(350.0, 0.001));
      expect(result.samples, [100, 200, 300, 400]);
    });

    test('5 samples averages the top 3 (odd rounds up)', () {
      final result = SpeedResult.topHalf([10, 20, 30, 40, 50]);
      expect(result.speedMbps, closeTo(40.0, 0.001));
    });

    test('empty list returns defaults', () {
      final result = SpeedResult.topHalf([]);
      expect(result.speedMbps, 0.0);
      expect(result.samples, isEmpty);
    });

    test('single sample returns that sample', () {
      final result = SpeedResult.topHalf([42.5]);
      expect(result.speedMbps, closeTo(42.5, 0.001));
    });
  });
}
