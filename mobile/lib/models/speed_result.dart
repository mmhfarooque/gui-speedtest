import 'dart:math' as math;

class SpeedResult {
  final double speedMbps;
  final List<double> samples;

  const SpeedResult({
    this.speedMbps = 0.0,
    this.samples = const [],
  });

  factory SpeedResult.topHalf(List<double> results) {
    if (results.isEmpty) {
      return const SpeedResult();
    }
    final sortedDesc = [...results]..sort((a, b) => b.compareTo(a));
    final cut = math.max(1, (sortedDesc.length + 1) ~/ 2);
    final top = sortedDesc.take(cut);
    final mean = top.reduce((a, b) => a + b) / cut;
    return SpeedResult(speedMbps: mean, samples: results);
  }
}
