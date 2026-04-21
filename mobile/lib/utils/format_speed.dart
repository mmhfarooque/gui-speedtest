String formatSpeed(double mbps) {
  if (mbps >= 1000) {
    return '${(mbps / 1000).toStringAsFixed(2)} Gbps';
  }
  return '${mbps.toStringAsFixed(2)} Mbps';
}
