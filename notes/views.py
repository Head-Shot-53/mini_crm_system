from django.shortcuts import render, get_object_or_404, redirect
from .models import Note
from .forms import NoteForm
from clients.models import Client
from django.contrib.auth.decorators import login_required

@login_required
def add_note(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.client = client
            note.save()
            return redirect('client_detail', pk=client.id)
    else:
        form = NoteForm()
    return render(request, 'notes/note_form.html', {'form':form, 'client':client})

@login_required
def edit_note(request, note_id):
    note = get_object_or_404(None, id = note_id)
    form = NoteForm(request.POST or None, instance=note)
    if form.is_valid():
        form.save()
        return redirect('client_dedtail', pk=note.client.id)

@login_required    
def delete_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    client_id = note.client.id
    if request.metho == 'POST':
        note.delete()
        return redirect('client_detail', pk=client_id)
    return render(request, 'notes/note_confirm_delete.html', {'note':note})
