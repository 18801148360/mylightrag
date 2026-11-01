import { useCallback, useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Plus, RefreshCw, ShieldCheck, UserRound, Users, X } from 'lucide-react'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Textarea from '@/components/ui/Textarea'
import Badge from '@/components/ui/Badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { useTranslation } from 'react-i18next'
import {
  addWorkspaceMember,
  archiveWorkspace,
  createUser,
  createWorkspace,
  getCurrentUser,
  listUsers,
  listWorkspaceMembers,
  listWorkspaces,
  removeWorkspaceMember,
  updateUser,
  updateWorkspace,
  updateWorkspaceMember,
  type ManagementUser,
  type ManagementWorkspace,
  type WorkspaceMember
} from '@/api/management'

type ManagementTab = 'workspaces' | 'users'

const errorText = (error: unknown): string => {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
  }
  return error instanceof Error ? error.message : 'Request failed'
}

const dateText = (value: string | null | undefined): string => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const ManagementPage = () => {
  const { t } = useTranslation()
  const [tab, setTab] = useState<ManagementTab>('workspaces')
  const [currentUser, setCurrentUser] = useState<ManagementUser | null>(null)
  const [users, setUsers] = useState<ManagementUser[]>([])
  const [workspaces, setWorkspaces] = useState<ManagementWorkspace[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null)
  const [members, setMembers] = useState<WorkspaceMember[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [showUserForm, setShowUserForm] = useState(false)
  const [showWorkspaceForm, setShowWorkspaceForm] = useState(false)
  const [userForm, setUserForm] = useState({
    username: '',
    password: '',
    display_name: '',
    role: 'user' as 'admin' | 'user'
  })
  const [workspaceForm, setWorkspaceForm] = useState({ name: '', slug: '', description: '' })
  const [memberUserId, setMemberUserId] = useState('')
  const [memberRole, setMemberRole] = useState<WorkspaceMember['role']>('viewer')

  const isAdmin = currentUser?.role === 'admin'
  const selectedWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === selectedWorkspaceId) ?? null,
    [selectedWorkspaceId, workspaces]
  )

  const roleLabel = (role: string) => t(`management.role.${role}`)
  const statusLabel = (status: string) => t(`management.status.${status}`)

  const loadMembers = useCallback(async (workspaceId: string) => {
    try {
      setMembers(await listWorkspaceMembers(workspaceId))
    } catch (error) {
      toast.error(errorText(error))
    }
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [me, workspaceItems] = await Promise.all([getCurrentUser(), listWorkspaces()])
      setCurrentUser(me)
      setWorkspaces(workspaceItems)
      setSelectedWorkspaceId((current) =>
        current && workspaceItems.some((workspace) => workspace.id === current)
          ? current
          : workspaceItems[0]?.id ?? null
      )
      if (me.role === 'admin') setUsers(await listUsers())
    } catch (error) {
      toast.error(errorText(error))
    } finally {
      setLoading(false)
    }
  }, [])

  // The initial request synchronizes this page with the control plane.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadData() }, [loadData])
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (selectedWorkspaceId) void loadMembers(selectedWorkspaceId)
    else setMembers([])
  }, [loadMembers, selectedWorkspaceId])

  const runBusy = async (action: () => Promise<void>) => {
    setBusy(true)
    try {
      await action()
    } catch (error) {
      toast.error(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  const handleCreateUser = async () => {
    if (!userForm.username || !userForm.password) {
      toast.error(t('management.usernamePasswordRequired'))
      return
    }
    await runBusy(async () => {
      await createUser(userForm)
      setUserForm({ username: '', password: '', display_name: '', role: 'user' })
      setShowUserForm(false)
      setUsers(await listUsers())
      toast.success(t('management.userCreated'))
    })
  }

  const handleToggleUser = async (user: ManagementUser) => {
    await runBusy(async () => {
      await updateUser(user.id, { status: user.status === 'active' ? 'disabled' : 'active' })
      setUsers(await listUsers())
      toast.success(t('management.userUpdated'))
    })
  }

  const handleResetPassword = async (user: ManagementUser) => {
    const password = window.prompt(t('management.newPasswordPrompt', { username: user.username }))
    if (!password) return
    await runBusy(async () => {
      await updateUser(user.id, { password })
      toast.success(t('management.passwordUpdated'))
    })
  }

  const handleCreateWorkspace = async () => {
    if (!workspaceForm.name || !workspaceForm.slug) {
      toast.error(t('management.nameSlugRequired'))
      return
    }
    await runBusy(async () => {
      const workspace = await createWorkspace(workspaceForm)
      setWorkspaceForm({ name: '', slug: '', description: '' })
      setShowWorkspaceForm(false)
      setWorkspaces(await listWorkspaces())
      setSelectedWorkspaceId(workspace.id)
      toast.success(t('management.workspaceCreated'))
    })
  }

  const handleArchiveWorkspace = async () => {
    if (!selectedWorkspace) return
    if (!window.confirm(t('management.archiveConfirm', { name: selectedWorkspace.name }))) return
    await runBusy(async () => {
      await archiveWorkspace(selectedWorkspace.id)
      const next = await listWorkspaces()
      setWorkspaces(next)
      setSelectedWorkspaceId(next[0]?.id ?? null)
      toast.success(t('management.workspaceArchived'))
    })
  }

  const handleSaveWorkspace = async () => {
    if (!selectedWorkspace) return
    await runBusy(async () => {
      await updateWorkspace(selectedWorkspace.id, {
        name: selectedWorkspace.name,
        description: selectedWorkspace.description
      })
      setWorkspaces(await listWorkspaces())
      toast.success(t('management.workspaceSaved'))
    })
  }

  const handleAddMember = async () => {
    if (!selectedWorkspace || !memberUserId) return
    await runBusy(async () => {
      await addWorkspaceMember(selectedWorkspace.id, { user_id: memberUserId, role: memberRole })
      setMemberUserId('')
      setMembers(await listWorkspaceMembers(selectedWorkspace.id))
      toast.success(t('management.memberAdded'))
    })
  }

  const handleMemberRole = async (member: WorkspaceMember, role: WorkspaceMember['role']) => {
    if (!selectedWorkspace) return
    await runBusy(async () => {
      await updateWorkspaceMember(selectedWorkspace.id, member.id, role)
      setMembers(await listWorkspaceMembers(selectedWorkspace.id))
    })
  }

  const handleRemoveMember = async (member: WorkspaceMember) => {
    if (!selectedWorkspace || !window.confirm(t('management.removeMemberConfirm', { username: member.username }))) return
    await runBusy(async () => {
      await removeWorkspaceMember(selectedWorkspace.id, member.id)
      setMembers(await listWorkspaceMembers(selectedWorkspace.id))
      toast.success(t('management.memberRemoved'))
    })
  }

  return (
    <div className="management-light min-h-full bg-zinc-50 p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">{t('management.title')}</h1>
            <p className="text-muted-foreground text-sm">{t('management.subtitle')}</p>
          </div>
          <Button variant="outline" onClick={() => void loadData()} disabled={loading || busy}>
            <RefreshCw className="size-4" /> {t('management.refresh')}
          </Button>
        </div>

        {loading ? <div className="text-muted-foreground py-12 text-center">{t('management.loading')}</div> : !currentUser ? null : (
          <>
            <div className="flex gap-2 border-b">
              <Button variant={tab === 'workspaces' ? 'default' : 'ghost'} onClick={() => setTab('workspaces')}>
                <Users className="size-4" /> {t('management.workspaces')}
              </Button>
              {isAdmin && <Button variant={tab === 'users' ? 'default' : 'ghost'} onClick={() => setTab('users')}>
                <UserRound className="size-4" /> {t('management.users')}
              </Button>}
            </div>

            {!isAdmin && <Card><CardContent className="flex items-center gap-3 py-5 text-sm"><ShieldCheck className="size-5" />{t('management.workspaceLevelAccess')}</CardContent></Card>}

            {tab === 'users' && isAdmin && (
              <Card>
                <CardHeader className="flex flex-row items-center justify-between"><CardTitle>{t('management.users')}</CardTitle><Button onClick={() => setShowUserForm((value) => !value)}><Plus className="size-4" /> {t('management.addUser')}</Button></CardHeader>
                <CardContent className="space-y-4">
                  {showUserForm && <div className="grid gap-3 rounded-lg border p-4 md:grid-cols-5">
                    <Input className="bg-input" placeholder={t('management.username')} value={userForm.username} onChange={(event) => setUserForm({ ...userForm, username: event.target.value })} />
                    <Input className="bg-input" type="password" placeholder={t('management.password')} value={userForm.password} onChange={(event) => setUserForm({ ...userForm, password: event.target.value })} />
                    <Input className="bg-input" placeholder={t('management.displayName')} value={userForm.display_name} onChange={(event) => setUserForm({ ...userForm, display_name: event.target.value })} />
                    <select className="border-input bg-input text-foreground h-9 rounded-md border px-3 text-sm" value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value as 'admin' | 'user' })}><option value="user">{roleLabel('user')}</option><option value="admin">{roleLabel('admin')}</option></select>
                    <div className="flex gap-2"><Button onClick={() => void handleCreateUser()} disabled={busy}>{t('management.create')}</Button><Button variant="ghost" onClick={() => setShowUserForm(false)}><X className="size-4" /></Button></div>
                  </div>}
                  <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">{t('management.username')}</th><th className="p-2">{t('management.roleHeader')}</th><th className="p-2">{t('management.statusHeader')}</th><th className="p-2">{t('management.lastLogin')}</th><th className="p-2">{t('management.action')}</th></tr></thead><tbody>{users.map((user) => <tr className="border-b" key={user.id}><td className="p-2"><div className="font-medium">{user.username}</div><div className="text-muted-foreground text-xs">{user.display_name}</div></td><td className="p-2"><Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>{roleLabel(user.role)}</Badge></td><td className="p-2"><Badge variant={user.status === 'active' ? 'outline' : 'destructive'}>{statusLabel(user.status)}</Badge></td><td className="p-2 text-muted-foreground">{dateText(user.last_login_at)}</td><td className="p-2"><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => void handleToggleUser(user)} disabled={busy || user.id === currentUser.id}>{user.status === 'active' ? t('management.disable') : t('management.activate')}</Button><Button variant="ghost" size="sm" onClick={() => void handleResetPassword(user)} disabled={busy}>{t('management.resetPassword')}</Button></div></td></tr>)}</tbody></table></div>
                </CardContent>
              </Card>
            )}

            {tab === 'workspaces' && <div className="grid gap-6 lg:grid-cols-[minmax(240px,0.8fr)_minmax(0,2fr)]">
              <Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle>{t('management.workspaces')}</CardTitle>{isAdmin && <Button size="sm" onClick={() => setShowWorkspaceForm((value) => !value)}><Plus className="size-4" /> {t('management.new')}</Button>}</CardHeader><CardContent className="space-y-3">
                {showWorkspaceForm && isAdmin && <div className="space-y-2 rounded-lg border p-3"><Input className="bg-input" placeholder={t('management.name')} value={workspaceForm.name} onChange={(event) => setWorkspaceForm({ ...workspaceForm, name: event.target.value })} /><Input className="bg-input" placeholder={t('management.slug')} value={workspaceForm.slug} onChange={(event) => setWorkspaceForm({ ...workspaceForm, slug: event.target.value })} /><Textarea className="bg-input" placeholder={t('management.description')} value={workspaceForm.description} onChange={(event) => setWorkspaceForm({ ...workspaceForm, description: event.target.value })} /><div className="flex gap-2"><Button onClick={() => void handleCreateWorkspace()} disabled={busy}>{t('management.create')}</Button><Button variant="ghost" onClick={() => setShowWorkspaceForm(false)}>{t('management.cancel')}</Button></div></div>}
                {workspaces.length === 0 && <p className="text-muted-foreground text-sm">{t('management.noWorkspaces')}</p>}
                {workspaces.map((workspace) => <button key={workspace.id} className={`w-full rounded-lg border p-3 text-left text-zinc-900 transition ${workspace.id === selectedWorkspaceId ? 'border-zinc-400 bg-zinc-100' : 'border-zinc-200 hover:bg-zinc-100'}`} onClick={() => setSelectedWorkspaceId(workspace.id)}><div className="flex items-center justify-between gap-2"><span className="font-medium">{workspace.name}</span><Badge variant={workspace.status === 'active' ? 'outline' : 'secondary'}>{statusLabel(workspace.status)}</Badge></div><div className="text-muted-foreground mt-1 text-xs">{workspace.slug}</div></button>)}
              </CardContent></Card>

              {selectedWorkspace && <div className="space-y-6"><Card><CardHeader className="flex flex-row items-center justify-between"><CardTitle>{t('management.workspaceDetails')}</CardTitle>{isAdmin && <div className="flex gap-2"><Button variant="outline" onClick={() => void handleSaveWorkspace()} disabled={busy}>{t('management.save')}</Button><Button variant="destructive" onClick={() => void handleArchiveWorkspace()} disabled={busy || selectedWorkspace.status === 'archived'}>{t('management.archive')}</Button></div>}</CardHeader><CardContent className="grid gap-3 md:grid-cols-2"><label className="space-y-1 text-sm"><span className="text-muted-foreground">{t('management.name')}</span><Input className="bg-input" disabled={!isAdmin} value={selectedWorkspace.name} onChange={(event) => setWorkspaces((items) => items.map((item) => item.id === selectedWorkspace.id ? { ...item, name: event.target.value } : item))} /></label><label className="space-y-1 text-sm"><span className="text-muted-foreground">{t('management.slug')}</span><Input className="bg-input" disabled value={selectedWorkspace.slug} /></label><label className="space-y-1 text-sm md:col-span-2"><span className="text-muted-foreground">{t('management.description')}</span><Textarea className="bg-input" disabled={!isAdmin} value={selectedWorkspace.description} onChange={(event) => setWorkspaces((items) => items.map((item) => item.id === selectedWorkspace.id ? { ...item, description: event.target.value } : item))} /></label></CardContent></Card>
                <Card><CardHeader><CardTitle>{t('management.members')}</CardTitle></CardHeader><CardContent className="space-y-4">{isAdmin && <div className="flex flex-wrap gap-2"><select className="border-input bg-input text-foreground h-9 min-w-48 rounded-md border px-3 text-sm" value={memberUserId} onChange={(event) => setMemberUserId(event.target.value)}><option value="">{t('management.selectUser')}</option>{users.filter((user) => !members.some((member) => member.id === user.id)).map((user) => <option key={user.id} value={user.id}>{user.username}</option>)}</select><select className="border-input bg-input text-foreground h-9 rounded-md border px-3 text-sm" value={memberRole} onChange={(event) => setMemberRole(event.target.value as WorkspaceMember['role'])}><option value="viewer">{roleLabel('viewer')}</option><option value="editor">{roleLabel('editor')}</option><option value="admin">{roleLabel('admin')}</option></select><Button onClick={() => void handleAddMember()} disabled={busy || !memberUserId}>{t('management.addMember')}</Button></div>}<div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">{t('management.user')}</th><th className="p-2">{t('management.roleHeader')}</th><th className="p-2">{t('management.statusHeader')}</th><th className="p-2">{t('management.action')}</th></tr></thead><tbody>{members.map((member) => <tr className="border-b" key={member.id}><td className="p-2">{member.username}<div className="text-muted-foreground text-xs">{member.display_name}</div></td><td className="p-2">{isAdmin ? <select className="border-input bg-input text-foreground h-8 rounded-md border px-2 text-sm" value={member.role} onChange={(event) => void handleMemberRole(member, event.target.value as WorkspaceMember['role'])}><option value="viewer">{roleLabel('viewer')}</option><option value="editor">{roleLabel('editor')}</option><option value="admin">{roleLabel('admin')}</option></select> : <Badge variant="secondary">{roleLabel(member.role)}</Badge>}</td><td className="p-2">{member.status}</td><td className="p-2">{isAdmin && <Button variant="ghost" size="sm" onClick={() => void handleRemoveMember(member)} disabled={busy}>{t('management.remove')}</Button>}</td></tr>)}</tbody></table></div></CardContent></Card>
              </div>}
            </div>}
          </>
        )}
      </div>
    </div>
  )
}

export default ManagementPage
