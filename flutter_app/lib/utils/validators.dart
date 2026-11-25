/// Client-side validators, ported from React core/validate.ts. The server validates again.
/// Each returns an error text, or null when the value is fine (Flutter FormField convention).
class Validators {
  Validators._();

  static final RegExp _email = RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$');

  static String? required(String? v, [String label = 'This field']) =>
      (v == null || v.trim().isEmpty) ? '$label is required.' : null;

  static String? _opt(String? v, bool req, String label, String? Function(String s) test) {
    if (v == null || v.trim().isEmpty) return req ? '$label is required.' : null;
    return test(v.trim());
  }

  static String? name(String? v, {String label = 'Name', bool required = false}) =>
      _opt(v, required, label, (s) => s.length < 2 ? '$label is too short.' : null);

  static String? mobile(String? v, {String label = 'Mobile', bool required = false}) => _opt(v, required, label,
      (s) => RegExp(r'^[6-9]\d{9}$').hasMatch(s) ? null : '$label must be 10 digits and start with 6, 7, 8 or 9.');

  static String? phone(String? v, {String label = 'Phone', bool required = false}) =>
      _opt(v, required, label, (s) => RegExp(r'^\+?\d{8,15}$').hasMatch(s) ? null : '$label must be 8 to 15 digits.');

  static String? email(String? v, {String label = 'Email', bool required = false}) =>
      _opt(v, required, label, (s) => _email.hasMatch(s) ? null : 'Enter a valid ${label.toLowerCase()}.');

  static String? pincode(String? v, {bool required = false}) =>
      _opt(v, required, 'Pincode', (s) => RegExp(r'^[1-9]\d{5}$').hasMatch(s) ? null : 'Pincode must be 6 digits.');

  static String? pan(String? v, {bool required = false}) => _opt(v, required, 'PAN',
      (s) => RegExp(r'^[A-Z]{5}\d{4}[A-Z]$').hasMatch(s) ? null : 'PAN looks like ABCDE1234F.');

  static String? ifsc(String? v, {bool required = false}) => _opt(v, required, 'IFSC',
      (s) => RegExp(r'^[A-Z]{4}0[A-Z0-9]{6}$').hasMatch(s) ? null : 'IFSC looks like HDFC0001234.');

  static String? gst(String? v, {bool required = false}) => _opt(v, required, 'GST number',
      (s) => RegExp(r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$').hasMatch(s)
          ? null
          : 'GST number must be 15 characters, like 27ABCDE1234F1Z5.');

  static String? upi(String? v, {bool required = false}) => _opt(v, required, 'UPI ID',
      (s) => RegExp(r'^[\w.\-]{2,}@[A-Za-z]{2,}$').hasMatch(s) ? null : 'UPI ID looks like name@bank.');

  static String? url(String? v, {bool required = false}) => _opt(v, required, 'Website',
      (s) => RegExp(r'^https?://[^\s.]+\.[^\s]{2,}$', caseSensitive: false).hasMatch(s)
          ? null
          : 'Website must start with http:// or https://');

  static String? password(String? v, [String label = 'Password']) =>
      (v == null || v.length < 8) ? '$label must be at least 8 characters.' : null;

  /// Login accepts a username OR an email in the same box.
  static String? loginId(String? v) {
    final s = (v ?? '').trim();
    if (s.isEmpty) return 'Enter your username or email.';
    if (s.contains('@') && !_email.hasMatch(s)) return 'That email address looks incomplete.';
    return null;
  }

  static String? integer(String? v, {String label = 'Value', bool required = false}) =>
      _opt(v, required, label, (s) => int.tryParse(s) == null ? '$label must be a whole number.' : null);

  static String? decimal(String? v, {String label = 'Value', bool required = false}) =>
      _opt(v, required, label, (s) => double.tryParse(s) == null ? '$label must be a number.' : null);

  /// Latitude/longitude pair: both or neither, within range.
  static String? latitude(String? v) => _opt(v, false, 'Latitude', (s) {
        final n = double.tryParse(s);
        return (n == null || n < -90 || n > 90) ? 'Latitude must be between -90 and 90.' : null;
      });
  static String? longitude(String? v) => _opt(v, false, 'Longitude', (s) {
        final n = double.tryParse(s);
        return (n == null || n < -180 || n > 180) ? 'Longitude must be between -180 and 180.' : null;
      });
}
