class BackendError implements Exception {
  final String message;

  const BackendError(this.message);

  @override
  String toString() => message;
}
