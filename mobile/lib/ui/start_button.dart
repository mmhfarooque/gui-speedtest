import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/test_runner.dart';

class StartButton extends StatelessWidget {
  const StartButton({super.key});

  @override
  Widget build(BuildContext context) {
    final runner = context.watch<TestRunner>();
    final (label, icon, onPressed) = switch (runner.phase) {
      TestPhase.idle => ('Start Speed Test', Icons.play_arrow, runner.start),
      TestPhase.done => ('Run Again', Icons.refresh, runner.start),
      TestPhase.error => ('Try Again', Icons.refresh, runner.start),
      _ => ('Cancel', Icons.stop, runner.cancel),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Center(
        child: FilledButton.icon(
          onPressed: onPressed,
          icon: Icon(icon),
          label: Text(label),
          style: FilledButton.styleFrom(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 20),
            textStyle: Theme.of(context).textTheme.titleMedium,
          ),
        ),
      ),
    );
  }
}
