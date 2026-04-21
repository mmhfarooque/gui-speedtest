import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../utils/log_manager.dart';

class LogViewerPage extends StatefulWidget {
  const LogViewerPage({super.key});

  @override
  State<LogViewerPage> createState() => _LogViewerPageState();
}

class _LogViewerPageState extends State<LogViewerPage> {
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _copyAll(BuildContext context, List<String> lines) {
    Clipboard.setData(ClipboardData(text: lines.join('\n')));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Copied ${lines.length} lines'),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  void _clear(BuildContext context) {
    LogManager.instance.clear();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Logs cleared'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final filePath = LogManager.instance.logFilePath;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Logs'),
        actions: [
          ValueListenableBuilder<List<String>>(
            valueListenable: LogManager.instance.logs,
            builder: (_, lines, _) => IconButton(
              tooltip: 'Copy all',
              icon: const Icon(Icons.copy_all_outlined),
              onPressed: lines.isEmpty ? null : () => _copyAll(context, lines),
            ),
          ),
          IconButton(
            tooltip: 'Clear logs',
            icon: const Icon(Icons.delete_outline),
            onPressed: () => _clear(context),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ValueListenableBuilder<List<String>>(
              valueListenable: LogManager.instance.logs,
              builder: (context, lines, _) {
                // Auto-scroll to bottom when new lines arrive.
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (_scrollController.hasClients) {
                    _scrollController.jumpTo(
                      _scrollController.position.maxScrollExtent,
                    );
                  }
                });
                if (lines.isEmpty) {
                  return const Center(child: Text('No log entries yet.'));
                }
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(12),
                  itemCount: lines.length,
                  itemBuilder: (context, i) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: SelectableText(
                      lines[i],
                      style: const TextStyle(
                        fontFamily: 'Menlo',
                        fontSize: 12,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          if (filePath != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: theme.colorScheme.surfaceContainerHighest,
                border: Border(
                  top: BorderSide(color: theme.colorScheme.outlineVariant),
                ),
              ),
              child: SelectableText(
                'Log file: $filePath',
                style: theme.textTheme.bodySmall?.copyWith(
                  fontFamily: 'Menlo',
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
