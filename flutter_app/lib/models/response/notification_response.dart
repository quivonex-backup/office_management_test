import '../common/ref.dart';

class AppNotification {
  final int id;
  final String eventCode, title, body;
  final String? referenceType;
  final int? referenceId;
  final String priority;
  final bool isRead;
  final String createdAt;
  const AppNotification({required this.id, required this.eventCode, required this.title, required this.body, this.referenceType,
      this.referenceId, required this.priority, required this.isRead, required this.createdAt});

  factory AppNotification.fromJson(Map<String, dynamic> j) => AppNotification(
        id: asInt(j['id']) ?? 0,
        eventCode: (j['event_code'] ?? '').toString(),
        title: (j['title'] ?? '').toString(),
        body: (j['body'] ?? '').toString(),
        referenceType: asStr(j['reference_type']),
        referenceId: asInt(j['reference_id']),
        priority: (j['priority'] ?? 'NORMAL').toString(),
        isRead: j['is_read'] == true,
        createdAt: (j['created_at'] ?? '').toString(),
      );
}

class NotificationPage {
  final int unreadCount;
  final List<AppNotification> notifications;
  final bool hasMore;
  const NotificationPage({required this.unreadCount, required this.notifications, required this.hasMore});

  factory NotificationPage.fromJson(Map<String, dynamic> j) => NotificationPage(
        unreadCount: asInt(j['unread_count']) ?? 0,
        hasMore: j['has_more'] == true,
        notifications: (j['notifications'] as List? ?? const [])
            .whereType<Map>()
            .map((e) => AppNotification.fromJson(Map<String, dynamic>.from(e)))
            .toList(),
      );
}
