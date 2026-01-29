# Conversation Instagram avec {conv_name}
ID: {conv_id}
Nombre de messages: {len(messages)}

Période: du {first_msg_date} au {last_msg_date}

Participants: {', '.join([decode_instagram_text(p.get('name', '')) for p in participants])}

Statistiques:
  • Médias partagés: {media_count}
{f'  • Liens partagés: {link_count}
' if link_count > 0 else ''}{f'  • Réactions totales: {reaction_count}
' if reaction_count > 0 else ''}{f'  • Appels: {call_count}
' if call_count > 0 else ''}