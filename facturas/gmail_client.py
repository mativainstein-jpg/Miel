import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config import GMAIL_SCOPES, CREDENTIALS_FILE, TOKEN_FILE, LABEL_PROCESADO


def autenticar():
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f'No se encontró credentials.json en {CREDENTIALS_FILE.parent}.\n'
                    'Seguí las instrucciones en SETUP.md para obtenerlo.'
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def buscar_pdfs_gmail(service):
    """Returns list of dicts with thread_id, message_id, filename, attachment_id, clave."""
    query = f'has:attachment filename:pdf -in:trash -in:drafts -label:{LABEL_PROCESADO}'
    resultados = []
    page_token = None

    while True:
        resp = service.users().messages().list(
            userId='me', q=query, pageToken=page_token, maxResults=100
        ).execute()

        for msg_ref in resp.get('messages', []):
            msg = service.users().messages().get(
                userId='me', id=msg_ref['id'], format='full'
            ).execute()

            thread_id = msg['threadId']
            message_id = msg['id']

            for part in _iter_parts(msg['payload']):
                filename = part.get('filename', '')
                if filename.lower().endswith('.pdf'):
                    attachment_id = part.get('body', {}).get('attachmentId')
                    if attachment_id:
                        resultados.append({
                            'thread_id':    thread_id,
                            'message_id':   message_id,
                            'filename':     filename,
                            'attachment_id': attachment_id,
                            'clave':        f'{message_id}|{filename}',
                        })

        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    return resultados


def descargar_adjunto(service, message_id, attachment_id):
    attachment = service.users().messages().attachments().get(
        userId='me', messageId=message_id, id=attachment_id
    ).execute()
    return base64.urlsafe_b64decode(attachment['data'])


def aplicar_label(service, thread_id, label_name=LABEL_PROCESADO):
    labels_resp = service.users().labels().list(userId='me').execute()
    label_id = next(
        (l['id'] for l in labels_resp.get('labels', []) if l['name'] == label_name),
        None
    )

    if not label_id:
        nuevo = service.users().labels().create(
            userId='me',
            body={'name': label_name, 'labelListVisibility': 'labelShow',
                  'messageListVisibility': 'show'}
        ).execute()
        label_id = nuevo['id']

    service.users().threads().modify(
        userId='me', id=thread_id, body={'addLabelIds': [label_id]}
    ).execute()


def _iter_parts(payload):
    if 'parts' in payload:
        for part in payload['parts']:
            yield from _iter_parts(part)
    else:
        yield payload
