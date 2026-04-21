import 'package:flutter/material.dart';

class MetricValue extends StatelessWidget {
  const MetricValue({
    super.key,
    required this.value,
    required this.loading,
    this.color,
  });

  final String? value;
  final bool loading;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (loading) {
      return const SizedBox(
        height: 28,
        width: 28,
        child: CircularProgressIndicator(strokeWidth: 2.5),
      );
    }
    return FittedBox(
      fit: BoxFit.scaleDown,
      alignment: Alignment.centerLeft,
      child: Text(
        (value == null || value!.isEmpty) ? '—' : value!,
        style: theme.textTheme.headlineMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: color,
        ),
        maxLines: 1,
      ),
    );
  }
}
