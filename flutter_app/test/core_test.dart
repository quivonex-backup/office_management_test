import 'package:flutter_test/flutter_test.dart';
import '../lib/api/api_response.dart';
import '../lib/utils/date_formatter.dart';
import '../lib/utils/error_handler.dart';
import '../lib/utils/validators.dart';

void main() {
  group('parseEnvelope', () {
    test('success envelope', () {
      final r = parseEnvelope(200, {'status': true, 'message': 'ok', 'data': {'a': 1}, 'errors': {}});
      expect(r.ok, isTrue);
      expect(r.message, 'ok');
    });

    test('field errors are joined per field', () {
      final r = parseEnvelope(400, {'status': false, 'message': 'Invalid', 'errors': {'email': ['Required.', 'Bad.']}});
      expect(r.ok, isFalse);
      expect(r.fieldErrors['email'], 'Required. Bad.');
    });

    test('empty failure message falls back to a status message', () {
      final r = parseEnvelope(403, {'status': false});
      expect(r.message, ErrorHandler.forStatus(403));
    });
  });

  group('validators', () {
    test('mobile', () {
      expect(Validators.mobile('9876543210'), isNull);
      expect(Validators.mobile('1234567890'), isNotNull);
    });
    test('email', () {
      expect(Validators.email('a@b.co'), isNull);
      expect(Validators.email('nope'), isNotNull);
    });
    test('login id accepts a username or an email', () {
      expect(Validators.loginId('john'), isNull);
      expect(Validators.loginId('john@'), isNotNull);
    });
  });

  group('DateFormatter', () {
    test('api date and time', () {
      expect(DateFormatter.api(DateTime(2025, 3, 1)), '2025-03-01');
      expect(DateFormatter.time('13:05:00'), '01:05 PM');
      expect(DateFormatter.date('2025-03-01'), '01 Mar 2025');
    });
  });
}
