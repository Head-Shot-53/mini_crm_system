from django.shortcuts import render, get_object_or_404, redirect
from .models import Client
from .forms import ClientForm
from django.contrib.auth.decorators import login_required

@login_required
def client_list(request):
    clients = Client.objects.all().order_by('-created_at')
    return render(request, 'clients/client_list.html', {'clients':clients})

@login_required
def client_create(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('client_list')
    else:
        form = ClientForm
    return render(request, 'clients/client_form.html', {'form':form})

@login_required
def client_update(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            return redirect('client_list')
    else:
        form = ClientForm(instance=client)
    return render(request, 'clients/client_form.html', {'form':form})

@login_required
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == 'POST':
        client.delete()
        return redirect('client_list')
    return render(request, 'clients/client_confirm_delete.html', {'client':client})

@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    notes = client.notes.all().order_by('-created_at')
    return render(request, 'clients/client_detail.html', {'client':client, 'notes':notes})