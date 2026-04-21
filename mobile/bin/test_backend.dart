import 'package:speedtest_mobile/backends/cloudflare.dart';
import 'package:speedtest_mobile/backends/progress_event.dart';
import 'package:speedtest_mobile/utils/format_speed.dart';

Future<void> main() async {
  final backend = CloudflareBackend();
  print('=== ${backend.displayName} smoke test ===\n');

  print('[1/4] Detecting connection...');
  final info = await backend.connectionInfo();
  print('  Server:   ${info.server}');
  print('  IP:       ${info.ip}');
  print('  ISP:      ${info.isp}');
  print('  Location: ${info.location}\n');

  print('[2/4] Measuring latency (10 samples)...');
  final lat = await backend.testLatency(
    samples: 10,
    onProgress: (e) {
      if (e is LatencySample) {
        print('  ${e.current}/${e.total}: ${e.valueMs.toStringAsFixed(1)} ms');
      }
    },
  );
  if (lat.failed) {
    print('  FAILED — all samples errored\n');
  } else {
    print('  avg ${lat.avg.toStringAsFixed(1)} ms  '
        'min ${lat.min.toStringAsFixed(1)}  '
        'max ${lat.max.toStringAsFixed(1)}  '
        'jitter ${lat.jitter.toStringAsFixed(1)}\n');
  }

  print('[3/4] Testing download...');
  try {
    final dl = await backend.testDownload(
      onProgress: (e) {
        if (e is DownloadChunk) {
          print('  chunk ${e.label}: ${formatSpeed(e.speedMbps)}');
        }
      },
    );
    print('  Download: ${formatSpeed(dl.speedMbps)}\n');
  } catch (e) {
    print('  FAILED: $e\n');
  }

  print('[4/4] Testing upload...');
  try {
    final ul = await backend.testUpload(
      onProgress: (e) {
        if (e is UploadChunk) {
          print('  chunk ${e.label}: ${formatSpeed(e.speedMbps)}');
        }
      },
    );
    print('  Upload:   ${formatSpeed(ul.speedMbps)}\n');
  } catch (e) {
    print('  FAILED: $e\n');
  }

  print('=== done ===');
}
