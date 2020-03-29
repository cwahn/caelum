from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, authenticate, logout
from django.core.exceptions import PermissionDenied
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from .tokens import account_activation_token, pw_reset_token
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.http import Http404

from .forms import UserCreationForm, UserChangeForm, YonseiVerificationForm, PasswordResetForm
from .models import User

from .yonsei_auth import verify

# Create your views here.


def landing(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_email_verified:
                login(request, user)
                return redirect('air:index')
            else:  # valid but pendig email verification
                form = AuthenticationForm()
                context = {
                    'form': form,
                    'account_error': 'Email verification is required. Please cheack your email for verification link.',
                }
                return render(request, 'accounts/landing.html', context)
        else:
            form = AuthenticationForm()
            context = {
                'form': form,
                'account_error': 'Invalid account.',
            }
            return render(request, 'accounts/landing.html', context)

    elif request.method == 'GET':
        form = AuthenticationForm()
        context = {
            'form': form,
        }
        return render(request, 'accounts/landing.html', context)


def verification(request):
    if request.method == 'POST':
        form = YonseiVerificationForm(request.POST)
        if form.is_valid() and form.cleaned_data.get('privacy_consent') == True:
            portal_id = form.cleaned_data.get('portal_id')
            portal_pw = form.cleaned_data.get('portal_pw')
            result, name, dept_major = verify(portal_id, portal_pw)
            name = name.lower().title()

            if result == True:

                if not User.objects.filter(portal_id=portal_id).exists():
                    request.session['pid'] = portal_id
                    request.session['name'] = name
                    request.session['dept_major'] = dept_major
                    request.session['verification'] = True

                    return redirect('accounts:sign_up')
                else:  # already a member
                    context = {
                        'title': 'Account already exists!',
                        'content': 'Looks like you already have an account. If you forgot your account information, you could find it through the link below the sign in form.',
                        'confirm': 'landing',
                    }
                    return render(request, 'accounts/message.html', context)
            else:  # not yonsei student
                context = {
                    'title': 'Sorry, student verification failed!',
                    'content': 'Please check if the Yonsei portal id and password are correct. For now, the community is only for the Yonsei University, Sinchon campus students. ',
                    'confirm': 'landing',
                }
                return render(request, 'accounts/message.html', context)
        else:
            return redirect('accounts:landing')

    elif request.method == 'GET':
        form = YonseiVerificationForm()
        context = {
            'form': form,
        }
        return render(request, 'accounts/verification.html', context)


def sign_up(request):
    if request.method == 'POST' and request.session['verification'] == True:
        form = UserCreationForm(
            request.POST,
            portal_id=request.session['pid'],
            name=request.session['name'],
            dept_major=request.session['dept_major']
        )
        if form.is_valid():
            user = form.save()

            current_site = get_current_site(request)
            mail_subject = 'Caelum email verification'
            message = render_to_string('accounts/verification-email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': account_activation_token.make_token(user),
            })
            to_email = user.email
            email = EmailMessage(
                mail_subject, message, to=[to_email]
            )
            email.send()

            request.session['verification'] == False

            context = {
                'title': 'Congratulations!',
                'content': "Welcome to Caelum, " + str(user.name).lower().title() + ". Your account activation mail just has been sent to " + str(user.email) + ". Please check your inbox and click the email verification link to activate your account. The activation link will be valid for a day. After expiration of the link you need to contact to administrator to resolve the problem. So, please do not miss the term and welcome again! ",
                'confirm': 'landing',
            }
            return render(request, 'accounts/message.html', context)

    elif request.method == 'GET':
        if request.session['verification'] == True:

            context = {
                'form': UserCreationForm(),
                'portal_id': request.session['pid'],
                'name': request.session['name'],
                'dept_major': request.session['dept_major'],
            }
            return render(request, 'accounts/sign-up.html', context)
        else:
            return redirect('accounts:landing')


def activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_email_verified = True
        user.save()
        login(request, user)
        # return redirect('home')
        context = {
            'title': "Congratulations!",
            'content': "Your email verification has been successful! Now you can sign in to Caelum. Welcome!",
            'confirm': 'index',
        }
        return render(request, 'accounts/message.html', context)
    else:
        raise Http404("Invalid access :(")
        return redirect('accounts:landing')


def find_account(request):
    if request.method == 'POST':
        form = YonseiVerificationForm(request.POST)
        if form.is_valid() and form.cleaned_data.get('privacy_consent') == True:
            portal_id = form.cleaned_data.get('portal_id')
            portal_pw = form.cleaned_data.get('portal_pw')
            result, name, dept_major = verify(portal_id, portal_pw)

            if result == True:

                if User.objects.filter(portal_id=portal_id).exists():
                    user = User.objects.get(portal_id=portal_id)

                    current_site = get_current_site(request)
                    mail_subject = 'Caelum password reset link.'
                    message = render_to_string('accounts/pw-reset-email.html', {
                        'user': user,
                        'domain': current_site.domain,
                        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                        'token': pw_reset_token.make_token(user),
                    })
                    to_email = user.email
                    email = EmailMessage(
                        mail_subject, message, to=[to_email]
                    )
                    email.send()

                    context = {
                        'title': 'Here is your account!',
                        'content': "\n" + str(user.email) + "\n\nPlease sign in with this account. In case if you don't remember the password, we just sent a mail to " + str(user.email) + ". Through the link in the mail, you could reset the password. The link will be valid up to two days.",
                        'confirm': 'landing',
                    }
                    return render(request, 'accounts/message.html', context)

                else:  # no account after the name
                    context = {
                        'title': "Sorry, there is no account!",
                        'content': "Looks like you don't have an account yet. You are welcome to join us any time.",
                        'confirm': 'landing',
                    }
                    return render(request, 'accounts/message.html', context)
            else:  # not yonsei student
                context = {
                    'title': 'Sorry, student verification failed!',
                    'content': 'Please check if the Yonsei portal id and password are correct. For now, the community is only for the Yonsei University, Sinchon campus students. ',
                    'confirm': 'landing',
                }
                return render(request, 'accounts/message.html', context)
        else:
            return redirect('accounts:landing')

    elif request.method == 'GET':
        form = YonseiVerificationForm()
        context = {
            'form': form,
        }
        return render(request, 'accounts/find-account.html', context)


def pw_reset(request, uidb64, token):
    if request.method == 'POST' and request.session['pw_reset'] == True:
        user = User.objects.get(pk=request.session['uid'])
        form = PasswordResetForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            request.session['pw_reset'] = False
            request.session['uid'] = False

            context = {
                    'title': "Your password has been chaged",
                    'content': 'Now you can sign in with your new password.',
                    'confirm': 'index',
                }
            return render(request, 'accounts/message.html', context)
        
        else:
            form = PasswordResetForm()
            user = User.objects.get(pk=request.session['uid'])
            context = {
                'email': str(user.email),
                'form': form,
                'error': 'Invalid password or those passwords did not match. Please try again.',
            }
            return render(request, 'accounts/pw-reset.html', context)


    elif request.method == 'GET':
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        if user is not None and pw_reset_token.check_token(user, token):
            form = PasswordResetForm()
            context = {
                'email': str(user.email),
                'form': form
            }
            request.session['pw_reset'] = True
            request.session['uid'] = str(uid)
            return render(request, 'accounts/pw-reset.html', context)

        else: # invaild token
            raise Http404("Invalid access :(")
            return redirect('accounts:landing')


   
def sign_out(request):
    logout(request)
    return redirect('accounts:landing')