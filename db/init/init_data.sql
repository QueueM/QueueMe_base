-- db/init/init_data.sql

-- Initial Permission Data
-- This creates the base permissions required by the system

-- Resource Permissions for Shops
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'shop', 'view'),
('b2c3d4e5-f6a7-8901-bcde-f12345678901', 'shop', 'add'),
('c3d4e5f6-a7b8-9012-cdef-123456789012', 'shop', 'edit'),
('d4e5f6a7-b8c9-0123-defg-2345678901234', 'shop', 'delete');

-- Resource Permissions for Services
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('e5f6a7b8-c9d0-1234-efgh-3456789012345', 'service', 'view'),
('f6a7b8c9-d0e1-2345-fghi-4567890123456', 'service', 'add'),
('a7b8c9d0-e1f2-3456-ghij-5678901234567', 'service', 'edit'),
('b8c9d0e1-f2a3-4567-hijk-6789012345678', 'service', 'delete');

-- Resource Permissions for Employees
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('c9d0e1f2-a3b4-5678-ijkl-7890123456789', 'employee', 'view'),
('d0e1f2a3-b4c5-6789-jklm-8901234567890', 'employee', 'add'),
('e1f2a3b4-c5d6-7890-klmn-9012345678901', 'employee', 'edit'),
('f2a3b4c5-d6e7-8901-lmno-0123456789012', 'employee', 'delete');

-- Resource Permissions for Specialists
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('a3b4c5d6-e7f8-9012-mnop-1234567890123', 'specialist', 'view'),
('b4c5d6e7-f8a9-0123-nopq-2345678901234', 'specialist', 'add'),
('c5d6e7f8-a9b0-1234-opqr-3456789012345', 'specialist', 'edit'),
('d6e7f8a9-b0c1-2345-pqrs-4567890123456', 'specialist', 'delete');

-- Resource Permissions for Customers
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('e7f8a9b0-c1d2-3456-qrst-5678901234567', 'customer', 'view'),
('f8a9b0c1-d2e3-4567-rstu-6789012345678', 'customer', 'add'),
('a9b0c1d2-e3f4-5678-stuv-7890123456789', 'customer', 'edit'),
('b0c1d2e3-f4a5-6789-tuvw-8901234567890', 'customer', 'delete');

-- Resource Permissions for Bookings
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('c1d2e3f4-a5b6-7890-uvwx-9012345678901', 'booking', 'view'),
('d2e3f4a5-b6c7-8901-vwxy-0123456789012', 'booking', 'add'),
('e3f4a5b6-c7d8-9012-wxyz-1234567890123', 'booking', 'edit'),
('f4a5b6c7-d8e9-0123-xyza-2345678901234', 'booking', 'delete');

-- Resource Permissions for Queue
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('a5b6c7d8-e9f0-1234-yzab-3456789012345', 'queue', 'view'),
('b6c7d8e9-f0a1-2345-zabc-4567890123456', 'queue', 'add'),
('c7d8e9f0-a1b2-3456-abcd-5678901234567', 'queue', 'edit'),
('d8e9f0a1-b2c3-4567-bcde-6789012345678', 'queue', 'delete');

-- Resource Permissions for Reports
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('e9f0a1b2-c3d4-5678-cdef-7890123456789', 'report', 'view'),
('f0a1b2c3-d4e5-6789-defg-8901234567890', 'report', 'add'),
('a1b2c3d4-e5f6-7890-efgh-9012345678901', 'report', 'edit'),
('b2c3d4e5-f6a7-8901-fghi-0123456789012', 'report', 'delete');

-- Resource Permissions for Content (Reels, Stories)
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('c3d4e5f6-a7b8-9012-ghij-1234567890123', 'reel', 'view'),
('d4e5f6a7-b8c9-0123-hijk-2345678901234', 'reel', 'add'),
('e5f6a7b8-c9d0-1234-ijkl-3456789012345', 'reel', 'edit'),
('f6a7b8c9-d0e1-2345-jklm-4567890123456', 'reel', 'delete'),
('a7b8c9d0-e1f2-3456-klmn-5678901234567', 'story', 'view'),
('b8c9d0e1-f2a3-4567-lmno-6789012345678', 'story', 'add'),
('c9d0e1f2-a3b4-5678-mnop-7890123456789', 'story', 'edit'),
('d0e1f2a3-b4c5-6789-nopq-8901234567890', 'story', 'delete');

-- Resource Permissions for Chat
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('e1f2a3b4-c5d6-7890-opqr-9012345678901', 'chat', 'view'),
('f2a3b4c5-d6e7-8901-pqrs-0123456789012', 'chat', 'add'),
('a3b4c5d6-e7f8-9012-qrst-1234567890123', 'chat', 'edit'),
('b4c5d6e7-f8a9-0123-rstu-2345678901234', 'chat', 'delete');

-- Resource Permissions for Payments
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('c5d6e7f8-a9b0-1234-stuv-3456789012345', 'payment', 'view'),
('d6e7f8a9-b0c1-2345-tuvw-4567890123456', 'payment', 'add'),
('e7f8a9b0-c1d2-3456-uvwx-5678901234567', 'payment', 'edit'),
('f8a9b0c1-d2e3-4567-vwxy-6789012345678', 'payment', 'delete');

-- Resource Permissions for Subscriptions
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('a9b0c1d2-e3f4-5678-wxyz-7890123456789', 'subscription', 'view'),
('b0c1d2e3-f4a5-6789-xyza-8901234567890', 'subscription', 'add'),
('c1d2e3f4-a5b6-7890-yzab-9012345678901', 'subscription', 'edit'),
('d2e3f4a5-b6c7-8901-zabc-0123456789012', 'subscription', 'delete');

-- Resource Permissions for Reviews
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('e3f4a5b6-c7d8-9012-abcd-1234567890123', 'review', 'view'),
('f4a5b6c7-d8e9-0123-bcde-2345678901234', 'review', 'add'),
('a5b6c7d8-e9f0-1234-cdef-3456789012345', 'review', 'edit'),
('b6c7d8e9-f0a1-2345-defg-4567890123456', 'review', 'delete');

-- Resource Permissions for Categories
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('c7d8e9f0-a1b2-3456-efgh-5678901234567', 'category', 'view'),
('d8e9f0a1-b2c3-4567-fghi-6789012345678', 'category', 'add'),
('e9f0a1b2-c3d4-5678-ghij-7890123456789', 'category', 'edit'),
('f0a1b2c3-d4e5-6789-hijk-8901234567890', 'category', 'delete');

-- Resource Permissions for Packages
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('a1b2c3d4-e5f6-7890-ijkl-9012345678901', 'package', 'view'),
('b2c3d4e5-f6a7-8901-jklm-0123456789012', 'package', 'add'),
('c3d4e5f6-a7b8-9012-klmn-1234567890123', 'package', 'edit'),
('d4e5f6a7-b8c9-0123-lmno-2345678901234', 'package', 'delete');

-- Resource Permissions for Discounts
INSERT INTO rolesapp_permission (id, resource, action) VALUES
('e5f6a7b8-c9d0-1234-mnop-3456789012345', 'discount', 'view'),
('f6a7b8c9-d0e1-2345-nopq-4567890123456', 'discount', 'add'),
('a7b8c9d0-e1f2-3456-opqr-5678901234567', 'discount', 'edit'),
('b8c9d0e1-f2a3-4567-pqrs-6789012345678', 'discount', 'delete');

-- Initial Roles
-- Queue Me Admin Role (has all permissions)
INSERT INTO rolesapp_role (id, name, description, role_type, is_active, created_at, updated_at, shop_id) VALUES
('c9d0e1f2-a3b4-5678-qrst-7890123456789', 'System Administrator', 'Full access to all system functionalities', 'queue_me_admin', 1, datetime('now'), datetime('now'), NULL);

-- Add all permissions to Queue Me Admin role
INSERT INTO rolesapp_role_permissions (id, role_id, permission_id)
SELECT hex(randomblob(16)), 'c9d0e1f2-a3b4-5678-qrst-7890123456789', id FROM rolesapp_permission;

-- Queue Me Employee Roles
INSERT INTO rolesapp_role (id, name, description, role_type, is_active, created_at, updated_at, shop_id) VALUES
('d0e1f2a3-b4c5-6789-rstu-8901234567890', 'Customer Support', 'Handle customer inquiries and issues', 'queue_me_employee', 1, datetime('now'), datetime('now'), NULL),
('e1f2a3b4-c5d6-7890-stuv-9012345678901', 'Content Manager', 'Manage platform content and messaging', 'queue_me_employee', 1, datetime('now'), datetime('now'), NULL),
('f2a3b4c5-d6e7-8901-tuvw-0123456789012', 'Sales Representative', 'Handle business onboarding and subscriptions', 'queue_me_employee', 1, datetime('now'), datetime('now'), NULL);

-- Shop Manager Role Template
INSERT INTO rolesapp_role (id, name, description, role_type, is_active, created_at, updated_at, shop_id) VALUES
('a3b4c5d6-e7f8-9012-uvwx-1234567890123', 'Shop Manager', 'Manages all aspects of a shop', 'shop_manager', 1, datetime('now'), datetime('now'), NULL);

-- Add shop management permissions to Shop Manager role
INSERT INTO rolesapp_role_permissions (id, role_id, permission_id)
SELECT hex(randomblob(16)), 'a3b4c5d6-e7f8-9012-uvwx-1234567890123', id FROM rolesapp_permission
WHERE resource IN ('shop', 'service', 'employee', 'specialist', 'booking', 'queue', 'review', 'reel', 'story', 'chat');

-- Shop Employee Role Templates
INSERT INTO rolesapp_role (id, name, description, role_type, is_active, created_at, updated_at, shop_id) VALUES
('b4c5d6e7-f8a9-0123-vwxy-2345678901234', 'Receptionist', 'Manage bookings and customer check-ins', 'shop_employee', 1, datetime('now'), datetime('now'), NULL),
('c5d6e7f8-a9b0-1234-wxyz-3456789012345', 'Customer Service', 'Handle customer inquiries and live chat', 'shop_employee', 1, datetime('now'), datetime('now'), NULL),
('d6e7f8a9-b0c1-2345-xyza-4567890123456', 'Marketing Manager', 'Manage shop content and promotions', 'shop_employee', 1, datetime('now'), datetime('now'), NULL);

-- Add viewing permissions to Receptionist role
INSERT INTO rolesapp_role_permissions (id, role_id, permission_id)
SELECT hex(randomblob(16)), 'b4c5d6e7-f8a9-0123-vwxy-2345678901234', id FROM rolesapp_permission
WHERE (resource IN ('booking', 'queue', 'customer', 'service') AND action = 'view')
   OR (resource = 'booking' AND action IN ('add', 'edit'))
   OR (resource = 'queue' AND action IN ('add', 'edit'));

-- Add customer service permissions
INSERT INTO rolesapp_role_permissions (id, role_id, permission_id)
SELECT hex(randomblob(16)), 'c5d6e7f8-a9b0-1234-wxyz-3456789012345', id FROM rolesapp_permission
WHERE (resource IN ('customer', 'chat', 'booking') AND action = 'view')
   OR (resource = 'chat' AND action IN ('add', 'edit'));

-- Add marketing permissions
INSERT INTO rolesapp_role_permissions (id, role_id, permission_id)
SELECT hex(randomblob(16)), 'd6e7f8a9-b0c1-2345-xyza-4567890123456', id FROM rolesapp_permission
WHERE (resource IN ('reel', 'story', 'service') AND action IN ('view', 'add', 'edit', 'delete'));

-- Initial Parent Categories
INSERT INTO categoriesapp_category (id, name_en, name_ar, description_en, description_ar, is_active, is_parent, parent_id, created_at, updated_at, image) VALUES
('e7f8a9b0-c1d2-3456-zabc-5678901234567', 'Beauty & Wellness', 'الجمال والصحة', 'Beauty and wellness services including hair, makeup, spa, and more', 'خدمات الجمال والعافية بما في ذلك الشعر والمكياج والسبا والمزيد', 1, 1, NULL, datetime('now'), datetime('now'), 'categories/beauty.jpg'),
('f8a9b0c1-d2e3-4567-abcd-6789012345678', 'Health & Medical', 'الصحة والطب', 'Health and medical services including doctors, dentists, and specialists', 'الخدمات الصحية والطبية بما في ذلك الأطباء وأطباء الأسنان والمتخصصين', 1, 1, NULL, datetime('now'), datetime('now'), 'categories/health.jpg'),
('a9b0c1d2-e3f4-5678-bcde-7890123456789', 'Home Services', 'خدمات المنزل', 'Home services including cleaning, maintenance, and repairs', 'خدمات المنزل بما في ذلك التنظيف والصيانة والإصلاحات', 1, 1, NULL, datetime('now'), datetime('now'), 'categories/home.jpg'),
('b0c1d2e3-f4a5-6789-cdef-8901234567890', 'Professional Services', 'الخدمات المهنية', 'Professional services including legal, financial, and consulting', 'الخدمات المهنية بما في ذلك الخدمات القانونية والمالية والاستشارية', 1, 1, NULL, datetime('now'), datetime('now'), 'categories/professional.jpg'),
('c1d2e3f4-a5b6-7890-defg-9012345678901', 'Automotive', 'السيارات', 'Automotive services including maintenance, repair, and detailing', 'خدمات السيارات بما في ذلك الصيانة والإصلاح والتفاصيل', 1, 1, NULL, datetime('now'), datetime('now'), 'categories/automotive.jpg');

-- Child Categories for Beauty & Wellness
INSERT INTO categoriesapp_category (id, name_en, name_ar, description_en, description_ar, is_active, is_parent, parent_id, created_at, updated_at, image) VALUES
('d2e3f4a5-b6c7-8901-efgh-0123456789012', 'Hair Salon', 'صالون الشعر', 'Hair cutting, styling, coloring, and treatment services', 'خدمات قص الشعر وتصفيفه وتلوينه ومعالجته', 1, 0, 'e7f8a9b0-c1d2-3456-zabc-5678901234567', datetime('now'), datetime('now'), 'categories/hair.jpg'),
('e3f4a5b6-c7d8-9012-fghi-1234567890123', 'Nails', 'الأظافر', 'Manicure, pedicure, and nail art services', 'خدمات المانيكير والباديكير وفن الأظافر', 1, 0, 'e7f8a9b0-c1d2-3456-zabc-5678901234567', datetime('now'), datetime('now'), 'categories/nails.jpg'),
('f4a5b6c7-d8e9-0123-ghij-2345678901234', 'Spa & Massage', 'سبا ومساج', 'Relaxation, therapeutic, and wellness massage services', 'خدمات المساج للاسترخاء والعلاج والعافية', 1, 0, 'e7f8a9b0-c1d2-3456-zabc-5678901234567', datetime('now'), datetime('now'), 'categories/spa.jpg'),
('a5b6c7d8-e9f0-1234-hijk-3456789012345', 'Skincare', 'العناية بالبشرة', 'Facials, treatments, and skincare services', 'خدمات العناية بالوجه والعلاجات والعناية بالبشرة', 1, 0, 'e7f8a9b0-c1d2-3456-zabc-5678901234567', datetime('now'), datetime('now'), 'categories/skin.jpg'),
('b6c7d8e9-f0a1-2345-ijkl-4567890123456', 'Makeup', 'مكياج', 'Professional makeup services for all occasions', 'خدمات المكياج الاحترافية لجميع المناسبات', 1, 0, 'e7f8a9b0-c1d2-3456-zabc-5678901234567', datetime('now'), datetime('now'), 'categories/makeup.jpg');

-- Child Categories for Health & Medical
INSERT INTO categoriesapp_category (id, name_en, name_ar, description_en, description_ar, is_active, is_parent, parent_id, created_at, updated_at, image) VALUES
('c7d8e9f0-a1b2-3456-jklm-5678901234567', 'Dental', 'طب الأسنان', 'Dental checkups, cleanings, and treatments', 'فحوصات الأسنان والتنظيف والعلاجات', 1, 0, 'f8a9b0c1-d2e3-4567-abcd-6789012345678', datetime('now'), datetime('now'), 'categories/dental.jpg'),
('d8e9f0a1-b2c3-4567-klmn-6789012345678', 'General Physician', 'طبيب عام', 'General health checkups and consultations', 'فحوصات واستشارات الصحة العامة', 1, 0, 'f8a9b0c1-d2e3-4567-abcd-6789012345678', datetime('now'), datetime('now'), 'categories/physician.jpg'),
('e9f0a1b2-c3d4-5678-lmno-7890123456789', 'Dermatology', 'الأمراض الجلدية', 'Skin, hair, and nail health services', 'خدمات صحة الجلد والشعر والأظافر', 1, 0, 'f8a9b0c1-d2e3-4567-abcd-6789012345678', datetime('now'), datetime('now'), 'categories/dermatology.jpg'),
('f0a1b2c3-d4e5-6789-mnop-8901234567890', 'Physiotherapy', 'العلاج الطبيعي', 'Physical therapy and rehabilitation services', 'خدمات العلاج الطبيعي وإعادة التأهيل', 1, 0, 'f8a9b0c1-d2e3-4567-abcd-6789012345678', datetime('now'), datetime('now'), 'categories/physiotherapy.jpg');

-- Child Categories for Home Services
INSERT INTO categoriesapp_category (id, name_en, name_ar, description_en, description_ar, is_active, is_parent, parent_id, created_at, updated_at, image) VALUES
('a1b2c3d4-e5f6-7890-nopq-9012345678901', 'Cleaning', 'تنظيف', 'Home and office cleaning services', 'خدمات تنظيف المنازل والمكاتب', 1, 0, 'a9b0c1d2-e3f4-5678-bcde-7890123456789', datetime('now'), datetime('now'), 'categories/cleaning.jpg'),
('b2c3d4e5-f6a7-8901-opqr-0123456789012', 'Maintenance', 'صيانة', 'Home maintenance and repair services', 'خدمات صيانة وإصلاح المنازل', 1, 0, 'a9b0c1d2-e3f4-5678-bcde-7890123456789', datetime('now'), datetime('now'), 'categories/maintenance.jpg'),
('c3d4e5f6-a7b8-9012-pqrs-1234567890123', 'Plumbing', 'سباكة', 'Plumbing installation and repair services', 'خدمات تركيب وإصلاح السباكة', 1, 0, 'a9b0c1d2-e3f4-5678-bcde-7890123456789', datetime('now'), datetime('now'), 'categories/plumbing.jpg'),
('d4e5f6a7-b8c9-0123-qrst-2345678901234', 'Electrical', 'كهربائي', 'Electrical installation and repair services', 'خدمات التركيب والإصلاح الكهربائية', 1, 0, 'a9b0c1d2-e3f4-5678-bcde-7890123456789', datetime('now'), datetime('now'), 'categories/electrical.jpg');

-- Initial Notification Templates (SMS)
INSERT INTO notificationsapp_notificationtemplate (id, type, channel, subject, body_en, body_ar, variables, is_active, created_at, updated_at) VALUES
('e5f6a7b8-c9d0-1234-rstu-3456789012345', 'appointment_confirmation', 'sms', 'Appointment Confirmation', 'Your appointment for {{service_name}} at {{shop_name}} has been confirmed for {{date}} at {{time}}. Your appointment ID is {{appointment_id}}.', 'تم تأكيد موعدك لـ {{service_name}} في {{shop_name}} يوم {{date}} الساعة {{time}}. رقم موعدك هو {{appointment_id}}.', '["service_name", "shop_name", "date", "time", "appointment_id"]', 1, datetime('now'), datetime('now')),
('f6a7b8c9-d0e1-2345-stuv-4567890123456', 'appointment_reminder', 'sms', 'Appointment Reminder', 'Reminder: Your appointment for {{service_name}} at {{shop_name}} is tomorrow at {{time}}. We look forward to seeing you!', 'تذكير: موعدك لـ {{service_name}} في {{shop_name}} غدًا الساعة {{time}}. نتطلع لرؤيتك!', '["service_name", "shop_name", "time"]', 1, datetime('now'), datetime('now')),
('a7b8c9d0-e1f2-3456-tuvw-5678901234567', 'queue_join_confirmation', 'sms', 'Queue Confirmation', 'You have joined the queue at {{shop_name}}. Your position is {{position}} with an estimated wait time of {{estimated_wait}} minutes. Your ticket number is {{ticket_number}}.', 'لقد انضممت إلى قائمة الانتظار في {{shop_name}}. موقعك هو {{position}} بوقت انتظار تقريبي {{estimated_wait}} دقيقة. رقم تذكرتك هو {{ticket_number}}.', '["shop_name", "position", "estimated_wait", "ticket_number"]', 1, datetime('now'), datetime('now')),
('b8c9d0e1-f2a3-4567-uvwx-6789012345678', 'queue_called', 'sms', 'Your Turn', 'It\'s your turn now at {{shop_name}}! Please proceed to the counter.', 'حان دورك الآن في {{shop_name}}! يرجى التوجه إلى الكاونتر.', '["shop_name"]', 1, datetime('now'), datetime('now')),
('c9d0e1f2-a3b4-5678-vwxy-7890123456789', 'payment_confirmation', 'sms', 'Payment Confirmation', 'Your payment of {{amount}} SAR for {{service_name}} has been confirmed. Thank you for your business!', 'تم تأكيد دفعتك البالغة {{amount}} ريال سعودي لـ {{service_name}}. شكرا لتعاملك معنا!', '["amount", "service_name"]', 1, datetime('now'), datetime('now'));

-- Initial Notification Templates (Push)
INSERT INTO notificationsapp_notificationtemplate (id, type, channel, subject, body_en, body_ar, variables, is_active, created_at, updated_at) VALUES
('d0e1f2a3-b4c5-6789-wxyz-8901234567890', 'appointment_confirmation', 'push', 'Booking Confirmed', 'Your appointment for {{service_name}} has been confirmed for {{date}} at {{time}}.', 'تم تأكيد موعدك لـ {{service_name}} يوم {{date}} الساعة {{time}}.', '["service_name", "date", "time"]', 1, datetime('now'), datetime('now')),
('e1f2a3b4-c5d6-7890-xyza-9012345678901', 'appointment_reminder', 'push', 'Appointment Reminder', 'Don\'t forget! Your appointment is in 1 hour at {{shop_name}}.', 'لا تنس! موعدك بعد ساعة واحدة في {{shop_name}}.', '["shop_name"]', 1, datetime('now'), datetime('now')),
('f2a3b4c5-d6e7-8901-yzab-0123456789012', 'queue_join_confirmation', 'push', 'Queue Joined', 'You are now in line at {{shop_name}}. Your position: {{position}}', 'أنت الآن في قائمة الانتظار في {{shop_name}}. موقعك: {{position}}', '["shop_name", "position"]', 1, datetime('now'), datetime('now')),
('a3b4c5d6-e7f8-9012-zabc-1234567890123', 'queue_called', 'push', 'Your Turn!', 'It\'s your turn now at {{shop_name}}! Please proceed to the counter.', 'حان دورك الآن في {{shop_name}}! يرجى التوجه إلى الكاونتر.', '["shop_name"]', 1, datetime('now'), datetime('now')),
('b4c5d6e7-f8a9-0123-abcd-2345678901234', 'new_message', 'push', 'New Message', 'New message from {{sender_name}}: {{message_preview}}', 'رسالة جديدة من {{sender_name}}: {{message_preview}}', '["sender_name", "message_preview"]', 1, datetime('now'), datetime('now'));

-- Initial Subscription Plans
INSERT INTO subscriptionapp_plan (id, name_en, name_ar, description_en, description_ar, price, price_halalas, duration_days, max_shops, max_services_per_shop, max_specialists_per_shop, max_employees_per_shop, features, is_active, created_at, updated_at) VALUES
('c5d6e7f8-a9b0-1234-bcde-3456789012345', 'Basic', 'أساسي', 'Essential features for small businesses with a single location', 'ميزات أساسية للشركات الصغيرة ذات الموقع الواحد', 199.00, 19900, 30, 1, 10, 5, 10, '{"stories": true, "reels": false, "packages": false, "discounts": false, "analytics": false}', 1, datetime('now'), datetime('now')),
('d6e7f8a9-b0c1-2345-cdef-4567890123456', 'Professional', 'احترافي', 'Advanced features for growing businesses with multiple specialists', 'ميزات متقدمة للشركات النامية مع متخصصين متعددين', 499.00, 49900, 30, 3, 30, 15, 30, '{"stories": true, "reels": true, "packages": true, "discounts": false, "analytics": true}', 1, datetime('now'), datetime('now')),
('e7f8a9b0-c1d2-3456-defg-5678901234567', 'Enterprise', 'شركات', 'Comprehensive solution for businesses with multiple locations', 'حل شامل للشركات ذات المواقع المتعددة', 999.00, 99900, 30, 10, 100, 50, 100, '{"stories": true, "reels": true, "packages": true, "discounts": true, "analytics": true}', 1, datetime('now'), datetime('now'));

-- Initial Regions (Saudi Arabia only)
INSERT INTO geoapp_region (id, name_en, name_ar, country_code, is_active, created_at, updated_at) VALUES
('f7e8d9c0-b1a2-3456-efgh-6789012345678', 'Riyadh', 'الرياض', 'SA', 1, datetime('now'), datetime('now')),
('a8b9c0d1-e2f3-4567-fghi-7890123456789', 'Makkah', 'مكة المكرمة', 'SA', 1, datetime('now'), datetime('now')),
('b9c0d1e2-f3a4-5678-ghij-8901234567890', 'Madinah', 'المدينة المنورة', 'SA', 1, datetime('now'), datetime('now')),
('c0d1e2f3-a4b5-6789-hijk-9012345678901', 'Eastern Province', 'المنطقة الشرقية', 'SA', 1, datetime('now'), datetime('now')),
('d1e2f3a4-b5c6-7890-ijkl-0123456789012', 'Asir', 'عسير', 'SA', 1, datetime('now'), datetime('now')),
('e2f3a4b5-c6d7-8901-jklm-1234567890123', 'Tabuk', 'تبوك', 'SA', 1, datetime('now'), datetime('now')),
('f3a4b5c6-d7e8-9012-klmn-2345678901234', 'Hail', 'حائل', 'SA', 1, datetime('now'), datetime('now')),
('a4b5c6d7-e8f9-0123-lmno-3456789012345', 'Northern Borders', 'الحدود الشمالية', 'SA', 1, datetime('now'), datetime('now')),
('b5c6d7e8-f9a0-1234-mnop-4567890123456', 'Jazan', 'جازان', 'SA', 1, datetime('now'), datetime('now')),
('c6d7e8f9-a0b1-2345-nopq-5678901234567', 'Najran', 'نجران', 'SA', 1, datetime('now'), datetime('now')),
('d7e8f9a0-b1c2-3456-opqr-6789012345678', 'Al-Baha', 'الباحة', 'SA', 1, datetime('now'), datetime('now')),
('e8f9a0b1-c2d3-4567-pqrs-7890123456789', 'Al-Jawf', 'الجوف', 'SA', 1, datetime('now'), datetime('now')),
('f9a0b1c2-d3e4-5678-qrst-8901234567890', 'Qassim', 'القصيم', 'SA', 1, datetime('now'), datetime('now'));

-- Initial Cities (Sample major cities in Saudi Arabia)
INSERT INTO geoapp_city (id, name_en, name_ar, region_id, latitude, longitude, is_active, created_at, updated_at) VALUES
('a0b1c2d3-e4f5-6789-rstu-9012345678901', 'Riyadh', 'الرياض', 'f7e8d9c0-b1a2-3456-efgh-6789012345678', 24.7136, 46.6753, 1, datetime('now'), datetime('now')),
('b1c2d3e4-f5a6-7890-stuv-0123456789012', 'Jeddah', 'جدة', 'a8b9c0d1-e2f3-4567-fghi-7890123456789', 21.4858, 39.1925, 1, datetime('now'), datetime('now')),
('c2d3e4f5-a6b7-8901-tuvw-1234567890123', 'Makkah', 'مكة', 'a8b9c0d1-e2f3-4567-fghi-7890123456789', 21.3891, 39.8579, 1, datetime('now'), datetime('now')),
('d3e4f5a6-b7c8-9012-uvwx-2345678901234', 'Madinah', 'المدينة', 'b9c0d1e2-f3a4-5678-ghij-8901234567890', 24.5247, 39.5692, 1, datetime('now'), datetime('now')),
('e4f5a6b7-c8d9-0123-vwxy-3456789012345', 'Dammam', 'الدمام', 'c0d1e2f3-a4b5-6789-hijk-9012345678901', 26.4207, 50.0888, 1, datetime('now'), datetime('now')),
('f5a6b7c8-d9e0-1234-wxyz-4567890123456', 'Khobar', 'الخبر', 'c0d1e2f3-a4b5-6789-hijk-9012345678901', 26.2172, 50.1971, 1, datetime('now'), datetime('now')),
('a6b7c8d9-e0f1-2345-xyza-5678901234567', 'Dhahran', 'الظهران', 'c0d1e2f3-a4b5-6789-hijk-9012345678901', 26.3041, 50.1143, 1, datetime('now'), datetime('now')),
('b7c8d9e0-f1a2-3456-yzab-6789012345678', 'Tabuk', 'تبوك', 'e2f3a4b5-c6d7-8901-jklm-1234567890123', 28.3998, 36.5714, 1, datetime('now'), datetime('now')),
('c8d9e0f1-a2b3-4567-zabc-7890123456789', 'Abha', 'أبها', 'd1e2f3a4-b5c6-7890-ijkl-0123456789012', 18.2164, 42.5053, 1, datetime('now'), datetime('now')),
('d9e0f1a2-b3c4-5678-abcd-8901234567890', 'Jazan', 'جازان', 'b5c6d7e8-f9a0-1234-mnop-4567890123456', 16.8892, 42.5611, 1, datetime('now'), datetime('now')),
('e0f1a2b3-c4d5-6789-bcde-9012345678901', 'Buraidah', 'بريدة', 'f9a0b1c2-d3e4-5678-qrst-8901234567890', 26.3591, 43.9818, 1, datetime('now'), datetime('now')),
('f1a2b3c4-d5e6-7890-cdef-0123456789012', 'Najran', 'نجران', 'c6d7e8f9-a0b1-2345-nopq-5678901234567', 17.4922, 44.1321, 1, datetime('now'), datetime('now'));

-- Create a default super admin user (to be used for initial setup)
INSERT INTO authapp_user (id, phone_number, user_type, email, is_staff, is_active, is_verified, profile_completed, date_joined, is_superuser) VALUES
('a2b3c4d5-e6f7-8901-defg-1234567890123', '9966889977', 'admin', 'admin@queueme.net', 1, 1, 1, 1, datetime('now'), 1);

-- Assign admin role to super admin
INSERT INTO rolesapp_userrole (id, user_id, role_id, assigned_at) VALUES
('b3c4d5e6-f7a8-9012-efgh-2345678901234', 'a2b3c4d5-e6f7-8901-defg-1234567890123', 'c9d0e1f2-a3b4-5678-qrst-7890123456789', datetime('now'));
