class ConnectionInfo {
  final String ip;
  final String isp;
  final String city;
  final String region;
  final String country;
  final String server;

  const ConnectionInfo({
    this.ip = 'Unknown',
    this.isp = 'Unknown',
    this.city = '',
    this.region = 'Unknown',
    this.country = '',
    this.server = '',
  });

  String get location {
    final parts = [city, region, country]
        .where((p) => p.isNotEmpty && p != 'Unknown')
        .toList();
    return parts.isEmpty ? 'Unknown' : parts.join(', ');
  }
}
