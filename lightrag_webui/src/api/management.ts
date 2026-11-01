import type { AxiosResponse } from 'axios'
import { axiosInstance } from '@/api/lightrag'

export type ManagementUser = {
  id: string
  username: string
  display_name: string
  role: 'admin' | 'user'
  status: 'active' | 'disabled'
  created_at: string
  updated_at: string
  last_login_at: string | null
}

export type ManagementWorkspace = {
  id: string
  name: string
  slug: string
  description: string
  storage_namespace: string
  status: 'active' | 'archived'
  owner_id: string
  created_at: string
  updated_at: string
  member_role?: 'admin' | 'editor' | 'viewer'
}

export type WorkspaceMember = {
  id: string
  username: string
  display_name: string
  status: 'active' | 'disabled'
  role: 'admin' | 'editor' | 'viewer'
  created_at: string
}

type ItemsResponse<T> = { items: T[] }

const unwrap = async <T>(request: Promise<AxiosResponse<T>>): Promise<T> => {
  const response = await request
  return response.data
}

export const getCurrentUser = () => unwrap<ManagementUser>(axiosInstance.get('/api/v1/auth/me'))

export const listUsers = async () =>
  (await unwrap<ItemsResponse<ManagementUser>>(axiosInstance.get('/api/v1/users'))).items

export const createUser = (payload: {
  username: string
  password: string
  display_name?: string
  role: 'admin' | 'user'
}) => unwrap<ManagementUser>(axiosInstance.post('/api/v1/users', payload))

export const updateUser = (userId: string, payload: {
  display_name?: string
  password?: string
  role?: 'admin' | 'user'
  status?: 'active' | 'disabled'
}) => unwrap<ManagementUser>(axiosInstance.patch(`/api/v1/users/${userId}`, payload))

export const listWorkspaces = async () =>
  (await unwrap<ItemsResponse<ManagementWorkspace>>(axiosInstance.get('/api/v1/workspaces'))).items

export const createWorkspace = (payload: {
  name: string
  slug: string
  description?: string
  storage_namespace?: string
}) => unwrap<ManagementWorkspace>(axiosInstance.post('/api/v1/workspaces', payload))

export const updateWorkspace = (workspaceId: string, payload: {
  name?: string
  description?: string
}) => unwrap<ManagementWorkspace>(axiosInstance.patch(`/api/v1/workspaces/${workspaceId}`, payload))

export const archiveWorkspace = (workspaceId: string) =>
  unwrap<{ status: string; workspace_id: string }>(
    axiosInstance.post(`/api/v1/workspaces/${workspaceId}/archive`)
  )

export const listWorkspaceMembers = async (workspaceId: string) =>
  (await unwrap<ItemsResponse<WorkspaceMember>>(
    axiosInstance.get(`/api/v1/workspaces/${workspaceId}/members`)
  )).items

export const addWorkspaceMember = (workspaceId: string, payload: {
  user_id: string
  role: WorkspaceMember['role']
}) => unwrap<WorkspaceMember>(
  axiosInstance.post(`/api/v1/workspaces/${workspaceId}/members`, payload)
)

export const updateWorkspaceMember = (workspaceId: string, userId: string, role: WorkspaceMember['role']) =>
  unwrap<WorkspaceMember>(
    axiosInstance.patch(`/api/v1/workspaces/${workspaceId}/members/${userId}`, { role })
  )

export const removeWorkspaceMember = (workspaceId: string, userId: string) =>
  unwrap<{ status: string }>(
    axiosInstance.delete(`/api/v1/workspaces/${workspaceId}/members/${userId}`)
  )

