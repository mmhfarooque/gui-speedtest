import 'dart:io';

import 'package:flutter/material.dart';
import 'package:logging/logging.dart';
import 'package:provider/provider.dart';

import 'state/test_runner.dart';
import 'ui/app.dart';
import 'utils/log_manager.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await LogManager.instance.init();

  Logger('Startup').info(
    'Speed Test 0.1.0 — ${Platform.operatingSystem} '
    '${Platform.operatingSystemVersion} — locale ${Platform.localeName} — '
    'log file: ${LogManager.instance.logFilePath}',
  );

  runApp(
    ChangeNotifierProvider(
      create: (_) => TestRunner(),
      child: const SpeedTestApp(),
    ),
  );
}
