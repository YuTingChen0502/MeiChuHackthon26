// Session history only: Runtime owns acquisition shutdown and durable deletion.
export function sessionDeletionConfirmation(row) {
  return `Delete “${row.song_name}”?\n\nActive listening will stop and this session’s history will be permanently deleted.\n\nYour song and uploaded reference will stay available.`;
}

export class SessionDeletion {
  pending = new Set();

  async request(row, {adapter, authoritative, confirm, onDeleted = () => {}, onPending = () => {}}) {
    const id = row.session_id;
    if (!authoritative || !adapter) return {deleted:false, blocked:true};
    if (this.pending.has(id)) return {deleted:false, pending:true};
    this.pending.add(id);
    try {
      if (!await confirm(sessionDeletionConfirmation(row))) return {deleted:false, cancelled:true};
      onPending(id);
      const result = await adapter.deleteSession(id);
      onDeleted(id);
      return result;
    } finally {
      this.pending.delete(id);
    }
  }
}
