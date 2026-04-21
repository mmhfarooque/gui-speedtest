import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/test_runner.dart';

class ErrorBanner extends StatelessWidget {
  const ErrorBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final runner = context.watch<TestRunner>();
    if (runner.phase != TestPhase.error || runner.errorText == null) {
      return const SizedBox.shrink();
    }
    final theme = Theme.of(context);
    return Tooltip(
      message: runner.errorText!,
      waitDuration: const Duration(milliseconds: 400),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: theme.colorScheme.errorContainer,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: theme.colorScheme.error, width: 1),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.error_outline,
              color: theme.colorScheme.onErrorContainer,
              size: 20,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                runner.errorText!,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onErrorContainer,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
