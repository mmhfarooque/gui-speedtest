import 'package:flutter_test/flutter_test.dart';
import 'package:speedtest_mobile/models/latency_result.dart';

void main() {
  group('LatencyResult.fromSamples', () {
    test('empty list -> failed=true', () {
      final result = LatencyResult.fromSamples([]);
      expect(result.failed, isTrue);
      expect(result.samples, 0);
    });

    test('computes avg/min/max/jitter on multiple samples', () {
      final result = LatencyResult.fromSamples([10, 20, 30, 40]);
      expect(result.failed, isFalse);
      expect(result.avg, closeTo(25.0, 0.001));
      expect(result.min, 10.0);
      expect(result.max, 40.0);
      expect(result.samples, 4);
      // sample stdev of [10,20,30,40] = sqrt(500/3) ≈ 12.9099
      expect(result.jitter, closeTo(12.9099, 0.001));
    });

    test('single sample -> jitter=0 (needs >=2 for stdev)', () {
      final result = LatencyResult.fromSamples([15.5]);
      expect(result.jitter, 0.0);
      expect(result.avg, 15.5);
      expect(result.samples, 1);
    });
  });
}
