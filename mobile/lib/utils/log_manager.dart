import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:logging/logging.dart';
import 'package:path_provider/path_provider.dart';

class LogManager {
  LogManager._();
  static final LogManager instance = LogManager._();

  static const int _maxLines = 500;

  final ValueNotifier<List<String>> logs = ValueNotifier<List<String>>(
    const <String>[],
  );

  String? _logFilePath;
  IOSink? _sink;

  String? get logFilePath => _logFilePath;

  Future<void> init() async {
    try {
      final base = await getApplicationSupportDirectory();
      final dir = Directory('${base.path}/logs');
      if (!dir.existsSync()) dir.createSync(recursive: true);
      final file = File('${dir.path}/speedtest.log');
      _logFilePath = file.path;
      _sink = file.openWrite(mode: FileMode.append);
    } catch (_) {
      // File sink unavailable — in-memory buffer still works.
    }

    Logger.root.level = Level.INFO;
    Logger.root.onRecord.listen(_onRecord);
  }

  void _onRecord(LogRecord r) {
    final line =
        '${r.time.toIso8601String()} ${r.level.name.padRight(7)} '
        '${r.loggerName}: ${r.message}';
    final current = logs.value;
    final next = current.length >= _maxLines
        ? [...current.sublist(current.length - _maxLines + 1), line]
        : [...current, line];
    logs.value = next;
    try {
      _sink?.writeln(line);
    } catch (_) {}
  }

  void clear() {
    logs.value = const <String>[];
    if (_logFilePath != null) {
      try {
        _sink?.flush();
        _sink?.close();
        File(_logFilePath!).writeAsStringSync('');
        _sink = File(_logFilePath!).openWrite(mode: FileMode.append);
      } catch (_) {}
    }
  }

  Future<void> dispose() async {
    await _sink?.flush();
    await _sink?.close();
    _sink = null;
  }
}
