import 'package:dischargeiq_mobile/config.dart';
import 'package:dischargeiq_mobile/services/person_store.dart';
import 'package:flutter/material.dart';

/// Always-visible control naming whose records are on screen, with switching
/// one tap away.
///
/// Established pattern in family health apps: an avatar and name anchored in
/// the app bar, opening a sheet to switch person or add one. It is preferred
/// over a separate "people" destination because it answers "whose record am I
/// looking at?" continuously rather than only while you are on that screen -
/// and mixing up two family members' medications is the failure this exists
/// to prevent.
///
/// It also removes the need to ask "who is this for?" after an upload: the
/// active person is already chosen and on screen before the upload starts.
class PersonSwitcher extends StatelessWidget {
  const PersonSwitcher({
    super.key,
    required this.active,
    required this.onChanged,
    required this.onManage,
  });

  /// Person whose documents are showing, or null when none exist yet.
  final Person? active;

  /// Called with the newly selected person after a switch or an add.
  final ValueChanged<Person?> onChanged;

  /// Opens the full people list for renaming, refiling and deleting.
  final VoidCallback onManage;

  Future<void> _openSheet(BuildContext context) async {
    final people = await PersonStore.list();
    if (!context.mounted) return;

    await showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (sheetCtx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 4, 20, 12),
              child: Text(
                'Whose records?',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
              ),
            ),
            // "All" first: it is the default and the escape hatch for anyone
            // who does not want profiles at all. Built in, so it carries no
            // edit or delete affordance.
            ListTile(
              leading: CircleAvatar(
                backgroundColor: active == null ? kTeal : kTealMid.withValues(alpha: 0.5),
                child: const Icon(Icons.groups_outlined,
                    color: Colors.white, size: 20),
              ),
              title: const Text('All'),
              subtitle: const Text('Everyone\'s documents'),
              trailing: active == null
                  ? const Icon(Icons.check_circle, color: kTeal)
                  : null,
              onTap: () async {
                await PersonStore.setActive(null);
                if (sheetCtx.mounted) Navigator.pop(sheetCtx);
                onChanged(null);
              },
            ),
            if (people.isNotEmpty) const Divider(height: 1),
            ...people.map((p) => ListTile(
                  leading: CircleAvatar(
                    backgroundColor:
                        p.id == active?.id ? kTeal : kTealMid.withValues(alpha: 0.5),
                    child: Text(
                      p.name.characters.first.toUpperCase(),
                      style: const TextStyle(
                          color: Colors.white, fontWeight: FontWeight.w700),
                    ),
                  ),
                  title: Text(p.name),
                  subtitle: Text(p.relationship.label),
                  trailing: p.id == active?.id
                      ? const Icon(Icons.check_circle, color: kTeal)
                      : null,
                  onTap: () async {
                    await PersonStore.setActive(p.id);
                    if (sheetCtx.mounted) Navigator.pop(sheetCtx);
                    onChanged(p);
                  },
                )),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.person_add_alt_1, color: kTeal),
              title: const Text('Add a person'),
              onTap: () async {
                Navigator.pop(sheetCtx);
                onManage();
              },
            ),
            ListTile(
              leading: const Icon(Icons.folder_outlined, color: kTeal),
              title: const Text('Manage people and documents'),
              onTap: () {
                Navigator.pop(sheetCtx);
                onManage();
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    // Null is the built-in All view, not an empty state.
    final label = active?.name ?? 'All';

    return InkWell(
      borderRadius: BorderRadius.circular(24),
      onTap: () => _openSheet(context),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              radius: 15,
              backgroundColor: active == null ? kTealMid : kTeal,
              child: active == null
                  ? const Icon(Icons.groups_outlined, size: 17, color: Colors.white)
                  : Text(
                      active!.name.characters.first.toUpperCase(),
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 13,
                      ),
                    ),
            ),
            const SizedBox(width: 8),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 130),
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: dark ? kTextPrimaryDark : kTextPrimaryLight,
                ),
              ),
            ),
            Icon(Icons.expand_more,
                size: 20, color: dark ? kTextSecondaryDark : kTextSecondaryLight),
          ],
        ),
      ),
    );
  }
}
