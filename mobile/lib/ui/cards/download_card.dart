import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../state/test_runner.dart';
import '../../utils/format_speed.dart';
import 'card_base.dart';
import 'metric_value.dart';

class DownloadCard extends StatelessWidget {
  const DownloadCard({super.key});

  @override
  Widget build(BuildContext context) {
    final runner = context.watch<TestRunner>();
    final mbps = runner.liveDownloadMbps;
    final loading = runner.phase == TestPhase.download && mbps == null;
    final theme = Theme.of(context);
    return CardBase(
      title: 'Download',
      child: MetricValue(
        value: mbps == null ? null : formatSpeed(mbps),
        loading: loading,
        color: theme.colorScheme.primary,
      ),
    );
  }
}
