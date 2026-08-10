import { KnowledgeUpload } from "@/features/uploads/uploads-api";

type KnowledgeUploadTableProps = {
  uploads: KnowledgeUpload[];
  loading: boolean;
  emptyLabel: string;
  showPartner?: boolean;
};

export function KnowledgeUploadTable({
  uploads,
  loading,
  emptyLabel,
  showPartner = false,
}: KnowledgeUploadTableProps) {
  const columnCount = showPartner ? 7 : 6;

  return (
    <div className="contributor-table-wrap upload-table-wrap">
      <table>
        <thead>
          <tr>
            <th>File</th>
            {showPartner ? <th>Partner</th> : null}
            <th>Type</th>
            <th>Size</th>
            <th>Status</th>
            <th>Uploaded</th>
            <th>Preview</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columnCount}>Loading uploads</td>
            </tr>
          ) : null}

          {!loading && uploads.length === 0 ? (
            <tr>
              <td colSpan={columnCount}>{emptyLabel}</td>
            </tr>
          ) : null}

          {!loading
            ? uploads.map((upload) => (
                <tr key={upload.upload_id}>
                  <td>
                    <strong>{upload.title}</strong>
                    <span>{upload.original_filename}</span>
                  </td>
                  {showPartner ? <td>{upload.partner_name ?? "Global"}</td> : null}
                  <td>{upload.content_type ?? "file"}</td>
                  <td>{formatFileSize(upload.file_size_bytes)}</td>
                  <td>
                    <span className={`status-pill ${upload.processing_status}`}>
                      {upload.processing_status}
                    </span>
                  </td>
                  <td>{formatDate(upload.created_at)}</td>
                  <td>{upload.text_preview ? trimPreview(upload.text_preview) : "Stored only"}</td>
                </tr>
              ))
            : null}
        </tbody>
      </table>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const kilobytes = bytes / 1024;
  if (kilobytes < 1024) {
    return `${kilobytes.toFixed(1)} KB`;
  }
  return `${(kilobytes / 1024).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(value));
}

function trimPreview(value: string): string {
  return value.length > 160 ? `${value.slice(0, 160)}...` : value;
}
