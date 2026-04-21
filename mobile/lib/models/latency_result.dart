import 'dart:math' as math;

class LatencyResult {
  final double avg;
  final double min;
  final double max;
  final double jitter;
  final int samples;
  final bool failed;

  const LatencyResult({
    this.avg = 0.0,
    this.min = 0.0,
    this.max = 0.0,
    this.jitter = 0.0,
    this.samples = 0,
    this.failed = false,
  });

  factory LatencyResult.fromSamples(List<double> times) {
    if (times.isEmpty) {
      return const LatencyResult(failed: true);
    }
    final mean = times.reduce((a, b) => a + b) / times.length;
    final minVal = times.reduce(math.min);
    final maxVal = times.reduce(math.max);
    final jit = times.length > 1 ? _sampleStdev(times, mean) : 0.0;
    return LatencyResult(
      avg: mean,
      min: minVal,
      max: maxVal,
      jitter: jit,
      samples: times.length,
    );
  }

  static double _sampleStdev(List<double> values, double mean) {
    final squaredDiffs = values.map((v) => math.pow(v - mean, 2).toDouble());
    final variance = squaredDiffs.reduce((a, b) => a + b) / (values.length - 1);
    return math.sqrt(variance);
  }
}
