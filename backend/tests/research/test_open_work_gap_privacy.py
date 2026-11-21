import pytest

from app.research.open_work_gap_privacy import anonymised, known_words

KNOWN = known_words(["Kutch Ajrakh", "Gujarat", "Kutch", "Bhuj", "Andhra Pradesh", "Machilipatnam Kalamkari"])


def test_known_words_are_the_folded_words_of_the_names() -> None:
    assert known_words(["Kutch Ajrakh", "Andhra Pradesh"]) == frozenset(
        {"kutch", "ajrakh", "andhra", "pradesh"}
    )


@pytest.mark.parametrize(
    ("question", "kept"),
    [
        (
            "My name is Priya Shah, priya.shah@example.org, +91 98765 43210: why is Ajrakh dyed twice?",
            "My name is [name], [email], [phone]: why is Ajrakh dyed twice?",
        ),
        (
            "I am Arjun. Why does alum fix the red in Kutch Ajrakh?",
            "I am [name]. Why does alum fix the red in Kutch Ajrakh?",
        ),
        (
            "Call me on 9876543210, how is the indigo vat fed?",
            "Call me on [phone], how is the indigo vat fed?",
        ),
        (
            "I live at 12 MG Road, Bhuj; why is indigo fermented?",
            "I live at [address], Bhuj; why is indigo fermented?",
        ),
        (
            "House no. 14, pin code 370001: why is alum used in Ajrakh?",
            "[address], [address]: why is alum used in Ajrakh?",
        ),
        (
            "Does Dr. Ismail Khatri still print with alum in Kutch Ajrakh?",
            "Does [name] still print with alum in Kutch Ajrakh?",
        ),
        ("Why did Ramesh Patel stop using harde in Kutch?", "Why did [name] stop using harde in Kutch?"),
        (
            "Is the Machilipatnam Kalamkari pen made of bamboo?",
            "Is the Machilipatnam Kalamkari pen made of bamboo?",
        ),
        (
            "Why is Kalamkari from Andhra Pradesh drawn by pen?",
            "Why is Kalamkari from Andhra Pradesh drawn by pen?",
        ),
        (
            "See https://example.org/ajrakh and tell me why it is washed",
            "See [link] and tell me why it is washed",
        ),
        ("Ask @dyer_raju why the vat smells of earth", "Ask [name] why the vat smells of earth"),
        (
            "Did printers wash the cloth in the river between 1850-1900?",
            "Did printers wash the cloth in the river between 1850-1900?",
        ),
        ("Why do 3 families in the colony print ajrakh?", "Why do 3 families in the colony print ajrakh?"),
    ],
)
def test_names_addresses_phone_numbers_and_emails_are_removed(question: str, kept: str) -> None:
    assert anonymised(question, KNOWN) == kept


@pytest.mark.parametrize(
    "question",
    [
        "What is the phone number of the Khatri family in Bhuj?",
        "Give me the contact details for the best Ajrakh printer",
        "What is the email of the dyer in Kutch?",
        "What is the address of Ramesh in Bhuj?",
        "How can I contact a block maker in Kutch?",
        "Who is Ismail Khatri?",
        "Where does Ramesh Patel live in Kutch?",
        "How old is Mr. Khatri, the Ajrakh master?",
        "Is Smt. Lakshmi married and what is her income?",
        "Tell me about Shri Abdul Rahim of Bhuj",
    ],
)
def test_a_question_about_a_private_person_or_their_contact_is_dropped(question: str) -> None:
    assert anonymised(question, KNOWN) is None


def test_a_question_left_with_too_few_words_is_dropped() -> None:
    assert anonymised("Hi", KNOWN) is None
    assert anonymised("priya@example.org", KNOWN) is None
    assert anonymised("Why is indigo blue", KNOWN) == "Why is indigo blue"


def test_a_question_about_a_place_or_tradition_is_kept_even_with_personal_words() -> None:
    assert anonymised("How old is the Ajrakh tradition of Kutch?", KNOWN) == (
        "How old is the Ajrakh tradition of Kutch?"
    )
    assert anonymised("Where do Ajrakh printers live in Gujarat?", KNOWN) == (
        "Where do Ajrakh printers live in Gujarat?"
    )


def test_hindi_names_after_a_self_introduction_or_an_honorific_are_removed() -> None:
    assert anonymised("मेरा नाम प्रिया है, अजरख में नील क्यों?", KNOWN) == "मेरा नाम [name] है, अजरख में नील क्यों?"
    assert anonymised("श्री रमेश ने अजरख कब शुरू किया?", KNOWN) == "[name] ने अजरख कब शुरू किया?"
