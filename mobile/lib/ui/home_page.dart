import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../state/test_runner.dart';
import 'cards/connection_card.dart';
import 'cards/download_card.dart';
import 'cards/jitter_card.dart';
import 'cards/ping_card.dart';
import 'cards/upload_card.dart';
import 'error_banner.dart';
import 'log_viewer_page.dart';
import 'start_button.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Speed Test'),
        actions: [
          IconButton(
            tooltip: 'View logs',
            icon: const Icon(Icons.article_outlined),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const LogViewerPage()),
            ),
          ),
        ],
      ),
      body: CallbackShortcuts(
        bindings: <ShortcutActivator, VoidCallback>{
          const SingleActivator(LogicalKeyboardKey.keyR, meta: true): () {
            final runner = context.read<TestRunner>();
            if (!runner.isRunning) runner.start();
          },
          const SingleActivator(LogicalKeyboardKey.period, meta: true): () {
            final runner = context.read<TestRunner>();
            if (runner.isRunning) runner.cancel();
          },
        },
        child: Focus(
          autofocus: true,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 720),
                child: Container(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: theme.colorScheme.outlineVariant,
                      width: 1.5,
                    ),
                    color: theme.colorScheme.surfaceContainerLowest,
                  ),
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: const [
                      StartButton(),
                      ErrorBanner(),
                      ConnectionCard(),
                      SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(child: DownloadCard()),
                          SizedBox(width: 12),
                          Expanded(child: UploadCard()),
                        ],
                      ),
                      SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(child: PingCard()),
                          SizedBox(width: 12),
                          Expanded(child: JitterCard()),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
