import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../state/test_runner.dart';
import 'card_base.dart';

class ConnectionCard extends StatelessWidget {
  const ConnectionCard({super.key});

  @override
  Widget build(BuildContext context) {
    final runner = context.watch<TestRunner>();
    final info = runner.connectionInfo;
    final connecting = runner.phase == TestPhase.connecting && info == null;

    if (connecting) {
      return const CardBase(
        title: 'Connection',
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: 8),
          child: SizedBox(
            height: 20,
            width: 20,
            child: CircularProgressIndicator(strokeWidth: 2.5),
          ),
        ),
      );
    }

    return CardBase(
      title: 'Connection',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Row(label: 'Server', value: info?.server),
          _Row(label: 'IP', value: info?.ip),
          _Row(label: 'ISP', value: info?.isp),
          _Row(label: 'Location', value: info?.location),
        ],
      ),
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});
  final String label;
  final String? value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final displayed = (value == null || value!.isEmpty) ? '—' : value!;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(
            child: Text(
              displayed,
              style: theme.textTheme.bodyMedium,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
