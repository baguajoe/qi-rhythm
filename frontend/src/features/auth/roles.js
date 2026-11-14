// Roles: instructor < admin (manages their organization) < superadmin (the Qi Rhythm team at
// Eye Forge Studios: also manages the platform-wide Qi Rhythm Library).
export const isAdmin = (instructor) => ['admin', 'superadmin'].includes(instructor?.role);
export const isSuperadmin = (instructor) => instructor?.role === 'superadmin';
