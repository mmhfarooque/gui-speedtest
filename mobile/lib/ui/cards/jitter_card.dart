import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../state/test_runner.dart';
import 'card_base.dart';
import 'metric_value.dart';

class JitterCard extends StatelessWidget {
  const JitterCard({super.key});

  @override
  Widget build(BuildContext context) {
    final runner = context.watch<TestRunner>();
    final lat = runner.latency;
    final loading = runner.phase == TestPhase.latency && lat == null;
    final value = (lat == null || lat.failed)
        ? null
        : '${lat.jitter.toStringAsFixed(1)} ms';
    return CardBase(
      title: 'Jitter',
      child: MetricValue(value: value, loading: loading),
    );
  }
}
