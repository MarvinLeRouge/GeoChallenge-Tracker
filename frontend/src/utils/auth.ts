import { ProfileBase, ProfileBaseApi } from "@/types/auth"

// Utilitaire de mapping API -> front
export const mapProfileBase = (api: ProfileBaseApi): ProfileBase => ({
    id: api._id,
    email: api.email,
    username: api.username,
    role: api.role,
})