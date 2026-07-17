/// Tests for the garden's calendar-season mapping (gamification: the garden
/// lives in real time). Pure function, so no widget pumping needed.
library;

import 'package:dischargeiq_mobile/widgets/garden_widgets.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('seasonOf maps every month to its season', () {
    const expected = {
      1: 'winter', 2: 'winter', 3: 'spring', 4: 'spring',
      5: 'spring', 6: 'summer', 7: 'summer', 8: 'summer',
      9: 'autumn', 10: 'autumn', 11: 'autumn', 12: 'winter',
    };
    for (final e in expected.entries) {
      expect(seasonOf(DateTime(2026, e.key, 15)), e.value,
          reason: 'month ${e.key}');
    }
  });
}
