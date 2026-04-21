import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:logging/logging.dart';

import '../models/connection_info.dart';
import '../models/latency_result.dart';
import '../models/speed_result.dart';
import '../utils/browser_ua.dart';
import 'backend_error.dart';
import 'progress_event.dart';
import 'speed_test_backend.dart';

final _log = Logger('Cloudflare');

const Duration _shortTimeout = Duration(seconds: 5);
const Duration _chunkTimeout = Duration(seconds: 30);
const int _progressEvery = 256 * 1024;
const Map<String, String> _browserHeaders = {'User-Agent': browserUa};

// More complete browser-like headers for /meta — helps bypass Cloudflare's
// bot-score rejection when plain UA alone isn't enough.
const Map<String, String> _metaHeaders = {
  'User-Agent': browserUa,
  'Accept': 'application/json,text/plain,*/*',
  'Accept-Language': 'en-US,en;q=0.9',
  'Sec-Fetch-Mode': 'cors',
  'Sec-Fetch-Site': 'same-origin',
  'Referer': 'https://speed.cloudflare.com/',
};

Map<String, String> _parseTrace(String body) {
  final out = <String, String>{};
  for (final line in const LineSplitter().convert(body)) {
    final eq = line.indexOf('=');
    if (eq > 0) out[line.substring(0, eq).trim()] = line.substring(eq + 1).trim();
  }
  return out;
}

/// Look up ISP + city via ipwho.is. Returns null on any failure.
/// Empty IP lets the service auto-detect our public IP.
Future<Map<String, String>?> _ipwhoLookup(String ip) async {
  try {
    final safeIp = Uri.encodeComponent(ip);
    final resp = await http
        .get(Uri.parse('$_ipwhoUrl$safeIp'), headers: _browserHeaders)
        .timeout(_shortTimeout);
    if (resp.statusCode != 200) return null;
    final data = jsonDecode(resp.body) as Map<String, dynamic>;
    if (data['success'] == false) return null;
    final connection = (data['connection'] as Map<String, dynamic>?) ?? const {};
    return {
      'ip': (data['ip'] as String?) ?? '',
      'isp': (connection['isp'] as String?) ??
          (connection['org'] as String?) ??
          'Unknown',
      'city': (data['city'] as String?) ?? '',
      'region': (data['region'] as String?) ?? '',
      'country_code': (data['country_code'] as String?) ?? '',
    };
  } catch (_) {
    return null;
  }
}

const String _downUrl = 'https://speed.cloudflare.com/__down?bytes={}';
const String _upUrl = 'https://speed.cloudflare.com/__up';
const String _metaUrl = 'https://speed.cloudflare.com/meta';
const String _traceUrl = 'https://www.cloudflare.com/cdn-cgi/trace';
const String _ipifyUrl = 'https://api.ipify.org?format=json';
const String _ipwhoUrl = 'https://ipwho.is/';

// (chunkBytes, label) — symmetric for download + upload so TCP has time to
// saturate. Asymmetric sizes under-measured fast links on the Linux parent.
const List<(int, String)> _downSizes = [
  (1000000, '1 MB'),
  (5000000, '5 MB'),
  (10000000, '10 MB'),
  (25000000, '25 MB'),
];
const List<(int, String)> _upSizes = _downSizes;

class CloudflareBackend extends SpeedTestBackend {
  @override
  String get name => 'cloudflare';

  @override
  String get displayName => 'Cloudflare';

  bool _cancelled = false;
  http.Client? _client;

  @override
  Future<ConnectionInfo> connectionInfo() async {
    try {
      final resp = await http
          .get(Uri.parse(_metaUrl), headers: _metaHeaders)
          .timeout(_shortTimeout);
      _log.info('/meta status=${resp.statusCode}');
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final colo = (data['colo'] as String?) ?? '';
        return ConnectionInfo(
          ip: (data['clientIp'] as String?) ?? 'Unknown',
          isp: (data['asOrganization'] as String?) ?? 'Unknown',
          city: (data['city'] as String?) ?? '',
          region: (data['region'] as String?) ?? 'Unknown',
          country: (data['country'] as String?) ?? '',
          server: 'Cloudflare $colo'.trim(),
        );
      }
    } catch (e) {
      _log.info('/meta failed: $e — falling through to trace');
    }

    Map<String, String> trace = {};
    try {
      final resp = await http
          .get(Uri.parse(_traceUrl), headers: _browserHeaders)
          .timeout(_shortTimeout);
      if (resp.statusCode == 200) trace = _parseTrace(resp.body);
    } catch (_) {}

    final ip = trace['ip'] ?? '';
    final colo = trace['colo'] ?? '';
    final country = trace['loc'] ?? '';

    // Enrichment: ipwho.is gives us ISP + city that trace doesn't have.
    if (ip.isNotEmpty) {
      final enriched = await _ipwhoLookup(ip);
      if (enriched != null) {
        _log.info('ipwho enrichment: isp=${enriched['isp']}');
        return ConnectionInfo(
          ip: ip,
          isp: enriched['isp'] ?? 'Unknown',
          city: enriched['city'] ?? '',
          region: enriched['region'] ?? 'Unknown',
          country: country.isNotEmpty ? country : (enriched['country_code'] ?? ''),
          server: colo.isEmpty ? 'Cloudflare' : 'Cloudflare $colo',
        );
      }
      return ConnectionInfo(
        ip: ip,
        country: country,
        server: colo.isEmpty ? 'Cloudflare' : 'Cloudflare $colo',
      );
    }

    try {
      final resp = await http.get(Uri.parse(_ipifyUrl)).timeout(_shortTimeout);
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        return ConnectionInfo(
          ip: (data['ip'] as String?) ?? 'Unknown',
          server: 'Cloudflare',
        );
      }
    } catch (_) {}

    return const ConnectionInfo(server: 'Cloudflare');
  }

  @override
  Future<LatencyResult> testLatency({
    int samples = 10,
    ProgressCallback? onProgress,
  }) async {
    _cancelled = false;
    final latencyUrl = Uri.parse(_downUrl.replaceFirst('{}', '0'));
    final times = <double>[];

    for (var i = 0; i < samples; i++) {
      if (_cancelled) break;
      try {
        final sw = Stopwatch()..start();
        final resp = await http
            .get(latencyUrl, headers: _browserHeaders)
            .timeout(_shortTimeout);
        // Read body to EOF — http.get already does this, but reference
        // it to ensure the compiler doesn't elide.
        resp.bodyBytes.length;
        sw.stop();
        final elapsedMs = sw.elapsedMicroseconds / 1000.0;
        times.add(elapsedMs);
        onProgress?.call(LatencySample(
          current: i + 1,
          total: samples,
          valueMs: elapsedMs,
        ));
      } catch (_) {
        // Individual sample failed — keep going, fromSamples handles
        // "all failed" → failed=true.
      }
    }
    return LatencyResult.fromSamples(times);
  }

  @override
  Future<SpeedResult> testDownload({ProgressCallback? onProgress}) async {
    _cancelled = false;
    _client = http.Client();
    final results = <double>[];
    try {
      for (var i = 0; i < _downSizes.length; i++) {
        if (_cancelled) break;
        final (size, label) = _downSizes[i];
        try {
          final req = http.Request(
            'GET',
            Uri.parse(_downUrl.replaceFirst('{}', size.toString())),
          );
          req.headers.addAll(_browserHeaders);
          final sw = Stopwatch()..start();
          final resp = await _client!.send(req).timeout(_chunkTimeout);
          var totalBytes = 0;
          var nextReport = _progressEvery;
          await for (final piece in resp.stream) {
            if (_cancelled) break;
            totalBytes += piece.length;
            if (totalBytes >= nextReport) {
              final elapsedSec = sw.elapsedMicroseconds / 1000000.0;
              if (elapsedSec > 0) {
                onProgress?.call(DownloadProgress(
                  label: label,
                  speedMbps: (totalBytes * 8) / (elapsedSec * 1000000),
                  bytes: totalBytes,
                  current: i + 1,
                  total: _downSizes.length,
                ));
              }
              nextReport += _progressEvery;
            }
          }
          sw.stop();
          final elapsedSec = sw.elapsedMicroseconds / 1000000.0;
          if (elapsedSec <= 0) continue;
          final speed = (totalBytes * 8) / (elapsedSec * 1000000);
          results.add(speed);
          _log.info(
              'Download chunk $label: ${speed.toStringAsFixed(2)} Mbps in ${elapsedSec.toStringAsFixed(2)}s');
          onProgress?.call(DownloadChunk(
            label: label,
            speedMbps: speed,
            current: i + 1,
            total: _downSizes.length,
          ));
        } catch (e) {
          _log.warning('Download chunk $label failed: $e');
          onProgress?.call(ChunkError(
            label: label,
            error: e.toString(),
            isDownload: true,
          ));
        }
      }
    } finally {
      _client?.close();
      _client = null;
    }
    if (results.isEmpty) {
      throw const BackendError('all download attempts failed');
    }
    return SpeedResult.topHalf(results);
  }

  @override
  Future<SpeedResult> testUpload({ProgressCallback? onProgress}) async {
    _cancelled = false;
    _client = http.Client();
    final results = <double>[];
    final rng = Random();
    try {
      for (var i = 0; i < _upSizes.length; i++) {
        if (_cancelled) break;
        final (size, label) = _upSizes[i];
        try {
          final body = Uint8List(size);
          for (var j = 0; j < size; j++) {
            body[j] = rng.nextInt(256);
          }
          final sw = Stopwatch()..start();
          final resp = await _client!.post(
            Uri.parse(_upUrl),
            headers: {
              ..._browserHeaders,
              'Content-Type': 'application/octet-stream',
            },
            body: body,
          ).timeout(_chunkTimeout);
          resp.bodyBytes.length; // drain
          sw.stop();
          final elapsedSec = sw.elapsedMicroseconds / 1000000.0;
          if (elapsedSec <= 0) continue;
          final speed = (size * 8) / (elapsedSec * 1000000);
          results.add(speed);
          _log.info(
              'Upload chunk $label: ${speed.toStringAsFixed(2)} Mbps in ${elapsedSec.toStringAsFixed(2)}s');
          onProgress?.call(UploadChunk(
            label: label,
            speedMbps: speed,
            current: i + 1,
            total: _upSizes.length,
          ));
        } catch (e) {
          _log.warning('Upload chunk $label failed: $e');
          onProgress?.call(ChunkError(
            label: label,
            error: e.toString(),
            isDownload: false,
          ));
        }
      }
    } finally {
      _client?.close();
      _client = null;
    }
    if (results.isEmpty) {
      throw const BackendError('all upload attempts failed');
    }
    return SpeedResult.topHalf(results);
  }

  @override
  void cancel() {
    _cancelled = true;
    _client?.close();
  }
}
