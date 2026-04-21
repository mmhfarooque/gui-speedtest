sealed class ProgressEvent {
  const ProgressEvent();
}

class LatencySample extends ProgressEvent {
  final int current;
  final int total;
  final double valueMs;
  const LatencySample({
    required this.current,
    required this.total,
    required this.valueMs,
  });
}

class DownloadChunk extends ProgressEvent {
  final String label;
  final double speedMbps;
  final int current;
  final int total;
  const DownloadChunk({
    required this.label,
    required this.speedMbps,
    required this.current,
    required this.total,
  });
}

class DownloadProgress extends ProgressEvent {
  final String label;
  final double speedMbps;
  final int bytes;
  final int current;
  final int total;
  const DownloadProgress({
    required this.label,
    required this.speedMbps,
    required this.bytes,
    required this.current,
    required this.total,
  });
}

class UploadChunk extends ProgressEvent {
  final String label;
  final double speedMbps;
  final int current;
  final int total;
  const UploadChunk({
    required this.label,
    required this.speedMbps,
    required this.current,
    required this.total,
  });
}

class UploadProgress extends ProgressEvent {
  final String label;
  final double speedMbps;
  final int bytes;
  final int current;
  final int total;
  const UploadProgress({
    required this.label,
    required this.speedMbps,
    required this.bytes,
    required this.current,
    required this.total,
  });
}

class ChunkError extends ProgressEvent {
  final String label;
  final String error;
  final bool isDownload;
  const ChunkError({
    required this.label,
    required this.error,
    required this.isDownload,
  });
}
