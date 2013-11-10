from django.db import models
from django import forms
from django.contrib.auth.models import User
import operator, datetime
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
import pdb
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Field, MultiField, HTML
from crispy_forms.bootstrap import *
from django.utils.text import capfirst
from persone.models import *

STATI=(('disponibile','Disponibile'),('ferie','In ferie'),('malattia','In malattia'),('indisponibile','Indisponibile'))

GIORNI=((1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5'), (6, '6'), (7, '7'))

class Calendario(models.Model):
	nome = models.CharField('Nome',max_length=20)
	priorita = models.IntegerField('priorita', default=0, )
	class Meta:
		ordering = ['priorita']
	def __unicode__(self):
		return '%s' % (self.nome)
		
class CalendarioForm(forms.ModelForm):
	class Meta:
		model = Calendario
	def __init__(self, *args, **kwargs):
		self.helper = FormHelper()
		self.helper.layout = Layout(
			Field('nome'),
			Field('priorita'),
			FormActions(
				Submit('save', 'Invia', css_class="btn-primary")
			)
		)
		super(CalendarioForm, self).__init__(*args, **kwargs)



class TipoTurno(models.Model):
	identificativo = models.CharField(max_length=30, blank=False)
	priorita = models.IntegerField('priorita', default=0, )
	msg_errore = models.TextField('Messaggio errore disponibilita', blank=True, null=True, help_text="Il messaggio viene visualizzato nel caso non sia possibile modificare la disponibilta")
	#msg_lontano = models.TextField( blank=True, null=True, )
	def __unicode__(self):
		return '%s' % (self.identificativo)

class TipoTurnoForm(forms.ModelForm):
	class Meta:
		model = TipoTurno
	def __init__(self, *args, **kwargs):
		self.helper = FormHelper()
		self.helper.layout = Layout(
			Field('identificativo'),
			Field('priorita'),
			Field('msg_errore'),
			FormActions(
				Submit('save', 'Invia', css_class="btn-primary")
			)
		)
		super(TipoTurnoForm, self).__init__(*args, **kwargs)



class Requisito(models.Model):
	mansione=models.ForeignKey(Mansione, related_name="req_mansione")
	minimo=models.IntegerField('Maggiore o uguale', default=0)
	massimo=models.IntegerField('Minore o uguale', default=0)
	tipo_turno=models.ForeignKey(TipoTurno, related_name="req_tipo_turno",)
	necessario=models.BooleanField('Necessario', default=True, help_text="Se selezionato il requisito deve essere soddisfatto")
	sufficiente=models.BooleanField('Sufficiente', default=False, help_text="Se il requisito e' soddisfatto il turno risulta coperto in ogni caso")
	nascosto=models.BooleanField('Nascosto', default=False, help_text="Se il requisito risulta nascosto verra comunque verificato ma la persona non potra' segnarsi in quel ruolo")
	extra=models.BooleanField('Extra', default=False, help_text="Il requisito viene verificato su tutte le capacita delle persone disponibili, indipendentemtne dal loro ruolo nel turno")
	def clickabile(self):
		return  not (self.extra or self.nascosto)
	def save(self, *args, **kwargs):
		super(Requisito, self).save(*args, **kwargs)
		for t in Turno.objects.filter(tipo=self.tipo_turno):
			t.coperto = t.calcola_coperto()
			t.save()
	def delete(self, *args, **kwargs):
		super(Requisito, self).delete(*args, **kwargs)
		for t in Turno.objects.filter(tipo=self.tipo_turno):
			t.coperto = t.calcola_coperto()
			t.save()

class RequisitoForm(forms.ModelForm):
	class Meta:
		model = Requisito
		exclude = ('tipo_turno')
	def __init__(self, *args, **kwargs):
		self.helper = FormHelper()
		self.helper.layout = Layout(
			Field('mansione'),
			Field('minimo'),
			Field('massimo'),
			Field('necessario'),
			Field('sufficiente'),
			Field('nascosto'),
			Field('extra'),
			FormActions(
				Submit('save', 'Invia', css_class="btn-primary")
			)
		)
		super(RequisitoForm, self).__init__(*args, **kwargs)
		
GIORNO = (
  (0, 'lunedi'),
  (1, 'martedi'),
  (2, 'mercoledi'),
  (3, 'giovedi'),
  (4, 'venerdi'),
  (5, 'sabato'),
  (6, 'domenica'),
  )

GIORNO_EXT = GIORNO + (
  (103, 'feriale'),
  (101, 'prefestivo'),
  (102, 'festivo'),
  (99, 'qualsiasi'),
  )

class FiltroCalendario(forms.Form):
	giorni = forms.MultipleChoiceField( label = "",	choices = GIORNO_EXT[0:10], required = False, )
	def __init__(self, *args, **kwargs):
		self.helper = FormHelper()
		self.helper.form_id = 'FiltroCalendario'
		self.helper.layout = Layout(
			InlineCheckboxes('giorni'),
			ButtonHolder( Submit('submit', 'Filtra', css_class='button white'), ),)
		self.helper.form_method = 'post'
		#self.helper.form_action = 'submit_survey'
		super(FiltroCalendario, self).__init__(*args, **kwargs)

class Occorrenza(models.Model):
	pass

class Turno(models.Model):
	identificativo = models.CharField(max_length=30, blank=True , default='')
	inizio = models.DateTimeField()
	fine = models.DateTimeField()
	tipo = models.ForeignKey(TipoTurno, blank=True, null=True, on_delete=models.SET_NULL)
	occorrenza = models.ForeignKey(Occorrenza, blank=True, null=True)
	valore = models.IntegerField('Punteggio',default=1)
	calendario = models.ForeignKey(Calendario, null=True, on_delete=models.SET_NULL, default=1)
	coperto = models.BooleanField(default=False)
	def verifica_requisito(self,requisito,mansione_id=0,persona_competenze=0):	
		if requisito.necessario:
			contatore=0
			if mansione_id!=0 and persona_competenze!=0:
				#p = Persona.objects.get(id=persona_id)
				#pdb.set_trace()
				if (not requisito.extra and requisito.mansione in capacita(mansione_id)):
					contatore+=1
				if (requisito.extra and requisito.mansione in persona_competenze):
					contatore+=1
			for d in self.turno_disponibilita.filter(tipo="Disponibile").exclude(mansione__isnull=True).all():
				if not requisito.extra:
					if (requisito.mansione in capacita(d.mansione.id)):
						contatore+=1
				else:
				 	if (requisito.mansione in d.persona.competenze.all() ):
						contatore+=1
				if contatore>requisito.massimo and requisito.massimo!=0:
					return False
			if contatore<requisito.minimo and requisito.minimo!=0:
				return False
			return True
		else:
			return True
	def gia_disponibili(self,requisito):
		return self.turno_disponibilita.filter(tipo="Disponibile",mansione=requisito.mansione).count()
	def calcola_coperto(self):
		if self.tipo:
			for r in Requisito.objects.filter(tipo_turno=self.tipo_id):
				if not self.verifica_requisito(r):
					return False
				elif r.sufficiente:
					return True
		return True
	def contemporanei(self):
		i=self.inizio+datetime.timedelta(seconds=60)
		f=self.fine-datetime.timedelta(seconds=60)
		return Turno.objects.filter( (models.Q(inizio__lte=i) & models.Q(fine__gte=f)) | models.Q(inizio__range=(i ,f)) | models.Q(fine__range=(i,f)) ).exclude(id=self.id)
	def mansioni(self):
		return Mansione.objects.filter(req_mansione__tipo_turno=self.tipo)
	def mansioni_indisponibili(self,persona):
		m_d=[]
		p=Persona.objects.get(id=persona)
		persona_competenze=p.competenze.all()
		#pdb.set_trace()
		for m in persona_competenze:
			for r in self.tipo.req_tipo_turno.all():
				if (self.verifica_requisito(r) and not self.verifica_requisito(r,mansione_id=m.id,persona_competenze=persona_competenze) ):
					m_d.append(m)
		return m_d
	def save(self, *args, **kwargs):
		self.inizio = self.inizio.replace(second=0)
		self.fine = self.fine.replace(second=0)
		super(Turno, self).save(*args, **kwargs)
		self.coperto = self.calcola_coperto()
		super(Turno, self).save(*args, **kwargs)

class TurnoForm(forms.ModelForm):
	modifica_futuri=forms.BooleanField(label="modifica occorrenze future",required=False, help_text="<i class='icon-warning-sign'></i> sara' modificato solo l'orario e non la data!")
	modifica_tutti=forms.BooleanField(label="modifica tutte le occorrenze",required=False, help_text="<i class='icon-warning-sign'></i> sara' modificato solo l'orario e non la data!")
	def __init__(self, *args, **kwargs):
		self.helper = FormHelper()
		self.helper.layout = Layout(
			Field('identificativo'),
			AppendedText(
				'inizio', '<i class="icon-calendar"></i>'
			),
			AppendedText(
				'fine', '<i class="icon-calendar"></i>'
			),
			Field('tipo'),
			Field('valore'),
			Field('calendario'),
			FormActions(
				Submit('save', 'Modifica', css_class="btn-primary")
			)
		)
		super(TurnoForm, self).__init__(*args, **kwargs)
		self.fields['tipo'].required = True
	class Meta:
		model = Turno
		exclude = ('occorrenza')
	def clean(self):
		data = self.cleaned_data
		if data.get('inizio')>data.get('fine'):
			raise forms.ValidationError('Il turno termina prima di iniziare! controlla inizio e fine')
		if (data.get('fine')-data.get('inizio')).days>0:
			raise forms.ValidationError('Il turno deve durare al massimo 24H')
		return data
		
class TurnoFormRipeti(TurnoForm):
	ripeti = forms.BooleanField(required=False)
	ripeti_da = forms.DateField(required=False)
	ripeti_al = forms.DateField(required=False)
	ripeti_il_giorno = forms.MultipleChoiceField(choices=GIORNO_EXT, widget=forms.CheckboxSelectMultiple(),required=False)
	def __init__(self, *args, **kwargs):
		self.helper = FormHelper()
		self.helper.layout = Layout(
			Field('identificativo'),
			AppendedText(
				'inizio', '<i class="icon-calendar"></i>'
			),
			AppendedText(
				'fine', '<i class="icon-calendar"></i>'
			),
			Field('tipo'),
			Field('valore'),
			Field('calendario'),
			Fieldset(
				'<span id="ripeti-switch" onclick="ripeti_toggle()"><i class="icon-chevron-down"></i> Ripeti turno</span>'
			),
			Div(
				Field('ripeti'),
				AppendedText(
					'ripeti_da', '<i class="icon-calendar"></i>'
				),
				AppendedText(
					'ripeti_al', '<i class="icon-calendar"></i>'
				),
				InlineCheckboxes('ripeti_il_giorno'), css_id="ripeti"
			),
			FormActions(
				Submit('save', 'Aggiungi', css_class="btn-primary")
			)
		)
		super(TurnoForm, self).__init__(*args, **kwargs)
		self.fields['tipo'].required = True
	def clean(self):
		data = self.cleaned_data
		ripeti=data.get('ripeti')
		da=data.get('ripeti_da')
		al=data.get('ripeti_al')
		if (data.get('fine')-data.get('inizio')).days>0:
			raise forms.ValidationError('Il turno deve durare al massimo 24H')
		if data.get('inizio')>data.get('fine'):
			raise forms.ValidationError('Il turno termina prima di iniziare! controlla inizio e fine')
		if ripeti and (da==None or al==None):
			raise forms.ValidationError('Specifica l\' intervallo in cui ripetere il turno')
		return data



DISPONIBILITA = (("Disponibile","Disponibile"),("Indisponibile","Indisponibile"),("Darichiamare","Da Richiamare"),("Nonrisponde","Non Risponde"),)

class Disponibilita(models.Model):
	tipo = models.CharField(max_length=20, choices=DISPONIBILITA)
	persona = models.ForeignKey(Persona, related_name='persona_disponibilita')
	ultima_modifica = models.DateTimeField()
	creata_da = models.ForeignKey(User, related_name='creata_da_disponibilita')
	turno = models.ForeignKey(Turno, related_name='turno_disponibilita')
	mansione = models.ForeignKey(Mansione, related_name='mansione_disponibilita',blank=True, null=True, on_delete=models.SET_NULL)
	note =  models.TextField( blank=True, null=True, default="")
	class Meta:
		ordering = ['mansione']
	def save(self, *args, **kwargs):
		super(Disponibilita, self).save(*args, **kwargs)
		self.turno.coperto = self.turno.calcola_coperto()
		self.turno.save()
	def delete(self, *args, **kwargs):
		super(Disponibilita, self).delete(*args, **kwargs)
		self.turno.coperto = self.turno.calcola_coperto()
		self.turno.save()

class Notifica(models.Model):
	destinatario = models.ForeignKey(User, related_name='destinatario_user')
	data =  models.DateTimeField()
	testo = models.CharField(max_length=1000)
	letto = models.BooleanField()
	

class Log(models.Model):
	testo = models.CharField(max_length=50)
	data = models.DateTimeField()

class UserCreationForm2(UserCreationForm):
	email = forms.EmailField(label = "Email")
	class Meta:
		model = User
		fields = ("username", "email", )

class UserChangeForm2(UserChangeForm):
	class Meta:
		model = User
		fields = ("username", "email",)
	def clean_password(self):
		return "" # This is a temporary fix for a django 1.4 bug
		
class Impostazioni_notifica(models.Model):
	utente = models.ForeignKey(User, related_name='impostazioni_notifica_utente', limit_choices_to = {'is_staff':True})
	giorni = MultiSelectField(max_length=250, blank=True, choices=GIORNO)
	tipo_turno = models.ManyToManyField(TipoTurno, blank=True, null=True)

class Impostazioni_notificaForm(forms.ModelForm):
	giorni = MultiSelectFormField(choices=GIORNO)
	class Meta:
		model = Impostazioni_notifica
	def __init__(self, *args, **kwargs):
		self.helper = FormHelper()
		self.helper.layout = Layout(
			Field('utente'),
			InlineCheckboxes('giorni'),
			InlineCheckboxes('tipo_turno'),
			FormActions(
				Submit('save', 'Aggiungi', css_class="btn-primary")
			)
		)
		super(Impostazioni_notificaForm, self).__init__(*args, **kwargs)
