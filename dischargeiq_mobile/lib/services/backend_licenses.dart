/// services/backend_licenses.dart
///
/// Registers the BACKEND's third-party dependencies with Flutter's
/// LicenseRegistry, so the in-app licence page shows the whole product rather
/// than half of it.
///
/// Why this is needed: showLicensePage() collects licences automatically, but
/// only for Dart and Flutter packages. DischargeIQ's analysis runs on a Python
/// backend the app cannot function without, and none of those dependencies
/// appear. A licence page that silently omits the half of the system doing the
/// actual work is worse than no page, because it looks complete.
///
/// LOF review action item, 26 Aug 2026 (36:04): include open-source licence
/// references and verify compliance within app documentation.
///
/// LIMITATION, stated rather than hidden. These entries are ATTRIBUTIONS -
/// package, version, licence name and project URL - not the full licence
/// texts. MIT, BSD and Apache-2.0 all require reproducing their text and
/// copyright notice in a distribution. Before any public store release the
/// full texts must be bundled as assets and read in here. For the current
/// direct-install beta this names every component and points at the complete
/// manifest, which is what the gate asked for; it is not yet full compliance
/// for a distributed binary.
library;

import 'package:flutter/foundation.dart';


/// One backend dependency worth naming on the licence page.
typedef _Dep = ({String name, String version, String licence, String url});

/// The backend dependencies that ship with the product.
///
/// Not the full 80-package transitive tree - that lives in DEPENDENCIES.md and
/// is regenerated with pip-licenses. This is the set a reader would recognise
/// as doing the work, plus the one flagged item, which is included precisely
/// BECAUSE it is the awkward one: a licence page that lists only the
/// comfortable dependencies is marketing, not attribution.
const List<_Dep> _backendDeps = [
  // Versions are the pins in requirements.lock.txt, verified against the
  // installed venv on 28 Aug 2026. An approximate version in a compliance
  // artefact is worse than none: it looks authoritative and is not.
  (name: 'FastAPI', version: '0.136.1', licence: 'MIT', url: 'https://github.com/fastapi/fastapi'),
  (name: 'Uvicorn', version: '0.46.0', licence: 'BSD-3-Clause', url: 'https://github.com/encode/uvicorn'),
  (name: 'Pydantic', version: '2.13.3', licence: 'MIT', url: 'https://github.com/pydantic/pydantic'),
  (name: 'python-multipart', version: '0.0.26', licence: 'Apache-2.0', url: 'https://github.com/Kludex/python-multipart'),
  (name: 'pdfplumber', version: '0.11.9', licence: 'MIT', url: 'https://github.com/jsvine/pdfplumber'),
  (name: 'pypdf', version: '6.10.2', licence: 'BSD-3-Clause', url: 'https://github.com/py-pdf/pypdf'),
  (name: 'pdfminer.six', version: '20251230', licence: 'MIT', url: 'https://github.com/pdfminer/pdfminer.six'),
  (name: 'pypdfium2', version: '5.7.1', licence: 'BSD-3-Clause / Apache-2.0', url: 'https://github.com/pypdfium2-team/pypdfium2'),
  (name: 'textstat', version: '0.7.13', licence: 'MIT', url: 'https://github.com/textstat/textstat'),
  (
    // The one flagged item, listed deliberately. See the compliance entry.
    name: 'Pyphen',
    version: '0.17.2',
    licence: 'GPLv2+ OR LGPLv2+ OR MPL 1.1 (used under LGPL/MPL, not GPL)',
    url: 'https://github.com/Kozea/Pyphen',
  ),
  (name: 'reportlab', version: '4.4.10', licence: 'BSD-3-Clause', url: 'https://www.reportlab.com/'),
  (name: 'asyncpg', version: '0.31.0', licence: 'Apache-2.0', url: 'https://github.com/MagicStack/asyncpg'),
  (name: 'Streamlit', version: '1.56.0', licence: 'Apache-2.0', url: 'https://github.com/streamlit/streamlit'),
  // Vertex AI and Cloud Text-to-Speech are reached over REST with ADC
  // credentials, so google-auth is the dependency and the google-cloud-*
  // client libraries are NOT installed. Listing those would be attribution
  // for software the product does not ship.
  (name: 'google-auth', version: '2.55.1', licence: 'Apache-2.0', url: 'https://github.com/googleapis/google-auth-library-python'),
  (name: 'openai (python)', version: '2.32.0', licence: 'Apache-2.0', url: 'https://github.com/openai/openai-python'),
  (name: 'anthropic (python)', version: '0.97.0', licence: 'MIT', url: 'https://github.com/anthropics/anthropic-sdk-python'),
  (name: 'requests', version: '2.33.1', licence: 'Apache-2.0', url: 'https://github.com/psf/requests'),
  (name: 'python-dotenv', version: '1.2.2', licence: 'BSD-3-Clause', url: 'https://github.com/theskumar/python-dotenv'),
];

/// The corpus is third-party material and belongs on this page too.
const String _dataAttribution = '''
Evaluation corpus: MTSamples transcribed medical reports, used de-identified
for accuracy testing only. Never shown to patients and not distributed with
the app.

Readability targets follow Flesch-Kincaid grade level. The 40-80% figure for
forgotten discharge information is from Kessels RPC, "Patients' memory for
medical information", Journal of the Royal Society of Medicine 2003;96:219-222.
''';

/// Register everything the automatic collector cannot see.
///
/// Call once during app startup, before any licence page can be opened.
/// LicenseRegistry accepts a lazy stream, so nothing is built unless a user
/// actually opens the page.
void registerBackendLicenses() {
  LicenseRegistry.addLicense(() async* {
    for (final dep in _backendDeps) {
      yield LicenseEntryWithLineBreaks(
        <String>['DischargeIQ backend', dep.name],
        '${dep.name} ${dep.version}\n\n'
        'Licence: ${dep.licence}\n'
        '${dep.url}\n\n'
        'Attribution summary. The full licence text is published by the '
        'project at the URL above and the complete dependency manifest, '
        'including the transitive tree, is in DEPENDENCIES.md in the '
        'DischargeIQ repository.',
      );
    }
    yield const LicenseEntryWithLineBreaks(
      <String>['DischargeIQ', 'Data and references'],
      _dataAttribution,
    );
    yield const LicenseEntryWithLineBreaks(
      <String>['DischargeIQ', 'Licence compliance'],
      'DischargeIQ is released under the Apache License 2.0.\n\n'
      'No AGPL or other network-copyleft component is used anywhere in the '
      'product. No GPL-only or LGPL-only component is used.\n\n'
      'Pyphen is tri-licensed (GPLv2+ OR LGPLv2+ OR MPL 1.1) and reaches the '
      'backend transitively through textstat, which provides the '
      'Flesch-Kincaid readability scoring. It is used under the LGPL or MPL '
      'option, never the GPL one, so it places no copyleft obligation on '
      'DischargeIQ. It is listed here rather than omitted because a licence '
      'page that shows only the uncomplicated dependencies is not attribution.',
    );
  });
  if (kDebugMode) {
    debugPrint('Registered ${_backendDeps.length} backend licence entries.');
  }
}
