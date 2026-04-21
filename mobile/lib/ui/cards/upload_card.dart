import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../state/test_runner.dart';
import '../../utils/format_speed.dart';
import 'card_base.dart';
import 'metric_value.dart';

class UploadCard extends StatelessWidget {
  const UploadCard({super.key});

  @override
  Widget build(BuildContext context) {
    final runner = context.watch<TestRunner>();
    final mbps = runner.liveUploadMbps;
    final loading = runner.phase == TestPhase.upload && mbps == null;
    final theme = Theme.of(context);
    return CardBase(
      title: 'Upload',
      child: MetricValue(
        value: mbps == null ? null : formatSpeed(mbps),
        loading: loading,
        color: theme.colorScheme.tertiary,
      ),
    );
  }
}
