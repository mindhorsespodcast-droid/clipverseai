from clipverse_worker.evaluation import scoring


def test_same_words_in_different_scripts_are_not_mistakes():
    ref = "Yeh galti 90% creators karte hain"
    assert scoring.wer(ref, "यह गलती 90% creators करते हैं") == 0
    assert scoring.wer(ref, "yeh galtee 90% creators karte hai") == 0  # spelling variants


def test_translation_is_a_mistake():
    ref = "maine samjhaya ki yeh habit sab badal deti hai"
    assert scoring.wer(ref, "I explained that this habit changes everything") > 0.7


def test_numbers_as_digits():
    assert scoring.numbers_as_digits("90% log ₹200 dete hain", "90% log 200 rupaye dete") == (2, 2)
    assert scoring.numbers_as_digits("90% log", "ninety percent log") == (1, 0)


def test_cer_is_kinder_than_wer():
    ref, hyp = "kya baat hai dosto", "kya bat he doston"
    assert scoring.cer(ref, hyp) <= scoring.wer(ref, hyp)


def test_script_mix():
    assert scoring.script_mix("मेरा favourite festival Diwali है") == 0.4
